"""Opt-in MCP connection hook for one persistent recovery worker per session."""
import argparse,json,math,os,subprocess,sys,time,uuid
from pathlib import Path
import win32api,win32con,win32event,win32process
from .automation.managed_session import process_identity,write_state
from .recovery_monitor import monitor_lock,validate_status_path
from .desktop_process import start_desktop_process
from .recovery_settings import recovery_settings

def observe_session_workers(session_file):
    # Import only for explicit legacy remediation, never on normal CAD calls.
    from .recovery_process_scan import observe_session_workers as observe
    return observe(session_file)

def _read_pending(path,session):
    raw=path.read_bytes();pending=json.loads(raw)
    if (pending.get('kind')!='recovery_worker_startup'
            or type(pending.get('pid')) is not int or pending['pid']<=0
            or not isinstance(pending.get('process_start_time'),str) or not pending['process_start_time']
            or pending.get('session_file')!=str(session.resolve())
            or not isinstance(pending.get('startup_token'),str) or not pending['startup_token']):
        raise RuntimeError('Recovery startup reservation identity/session is invalid; preserving evidence')
    return raw,pending

def _assert_current(session,expected):
    latest=json.loads(session.read_text(encoding='utf-8'))
    if ((latest.get('pid'),latest.get('start_time'))!=(expected.get('pid'),expected.get('start_time'))
            or process_identity(int(expected['pid']))!=expected['start_time']):
        raise RuntimeError('Recovery session target changed during startup reconciliation')

def _require_absent_worker(record):
    if (type(record.get('worker_pid')) is not int or record['worker_pid']<=0
            or not isinstance(record.get('worker_start_time'),str) or not record['worker_start_time']):
        raise RuntimeError('Recovery worker identity is unknown; no reservation was retired')
    # A live reused PID is not permission to retire; access denial propagates.
    if worker_identity(record['worker_pid']) is not None:
        raise RuntimeError('Recovery worker is live or its PID was reused; no reservation was retired')

def _require_absent_launcher(record):
    if (type(record.get('launcher_pid')) is not int or record['launcher_pid']<=0
            or not isinstance(record.get('launcher_start_time'),str) or not record['launcher_start_time']):
        raise RuntimeError('Recovery launcher identity is unknown; preserving the reservation')
    if worker_identity(record['launcher_pid']) is not None:
        raise RuntimeError('Recovery launcher is live or its PID was reused; preserving the reservation')

def _archive_directory(directory):
    archive=directory/'retired-startups'
    if archive.resolve().parent!=directory.resolve():
        raise RuntimeError('Recovery archive path leaves the private directory; preserving evidence')
    archive.mkdir(exist_ok=True)
    return archive

def _archive_pending(directory,pending_path,raw,status_path=None,status_raw=None):
    if pending_path.read_bytes()!=raw:
        raise RuntimeError('Recovery reservation changed during observation; preserving it')
    if status_path is not None and status_path.read_bytes()!=status_raw:
        raise RuntimeError('Recovery status changed during observation; preserving it')
    archive=_archive_directory(directory)
    name=uuid.uuid4().hex
    destination=archive/(name+'-worker-startup.json')
    # Both session mutexes are held; preserve original bytes, never unlink them.
    if status_path is not None:os.replace(status_path,archive/(name+'-monitor.json'))
    os.replace(pending_path,destination)
    return destination

def _retire_terminal_pending(session,directory,expected):
    """Called with launch mutex held. Do not infer death from launch timeout."""
    with monitor_lock(session):
        path=directory/'worker-startup.json';raw,pending=_read_pending(path,session)
        _assert_current(session,expected)
        if (directory/'requested.stop').exists():
            raise RuntimeError('Recovery stop marker exists; monitor remains stopped')
        differs=(pending['pid'],pending['process_start_time'])!=(int(expected['pid']),expected['start_time'])
        if differs and process_identity(pending['pid']) is not None:
            raise RuntimeError('Previous recovery target is live or its PID was reused; refusing retirement')
        status=directory/'monitor.json';status_raw=status.read_bytes() if status.exists() else None
        observed=json.loads(status_raw) if status_raw is not None else None
        known=(pending if pending.get('protocol_version')==2 and pending.get('worker_pid') else observed)
        if observed is not None and (observed.get('startup_token')!=pending['startup_token']
                or observed.get('session_file')!=str(session.resolve())
                or (observed.get('pid'),observed.get('process_start_time'))!=(pending['pid'],pending['process_start_time'])):
            raise RuntimeError('Recovery startup remains unconfirmed; old status cannot release reservation')
        failed_before_start=(pending.get('protocol_version')==2
                             and pending.get('launch_state')=='failed_before_process_creation')
        if not failed_before_start:
            if known is None:
                if pending.get('protocol_version')!=2 or pending.get('launcher_pid') is None:
                    raise RuntimeError(_unconfirmed_message(session,directory))
                # A dead venv launcher alone cannot establish real worker death.
                _require_absent_launcher(pending)
                if observe_session_workers(session):
                    raise RuntimeError('A same-session worker or launcher remains live; no retry allowed')
            else:
                _require_absent_worker(known)
                if pending.get('launcher_pid') is not None:_require_absent_launcher(pending)
        _assert_current(session,expected)
        if status_raw is None and status.exists():
            raise RuntimeError('Recovery status appeared during observation; preserving the reservation')
        return _archive_pending(directory,path,raw,status if observed is not None else None,status_raw)

def _unconfirmed_message(session,directory):
    command=subprocess.list2cmdline([sys.executable,'-m','solidworks_mcp.recovery_service',
        '--retire-stale-startup','--session-file',str(session),'--directory',str(directory)])
    return ('Recovery startup remains unconfirmed; no replacement was launched. '
            'Preserve the reservation. Inspect/retire only a proven terminal same-session '
            'attempt with the guarded command (unknown or live workers will be refused): '+command)

def retire_stale_startup(session_file,directory):
    """Explicit legacy repair: preserve evidence; never launch, attach or kill CAD."""
    session=Path(session_file);directory=Path(directory)
    if not session.is_absolute() or not directory.is_absolute():
        raise ValueError('Recovery remediation paths must be absolute')
    status=directory/'monitor.json';path=directory/'worker-startup.json'
    with monitor_lock(str(session)+'.worker-launch'),monitor_lock(session):
        validate_status_path(directory,status,session)
        expected=json.loads(session.read_text(encoding='utf-8'))
        _assert_current(session,expected)
        raw,pending=_read_pending(path,session)
        if (directory/'requested.stop').exists():
            raise RuntimeError('Recovery stop marker exists; preserving the reservation')
        same_target=(pending['pid'],pending['process_start_time'])==(int(expected['pid']),expected['start_time'])
        if same_target and not (pending.get('protocol_version')==2 and
                (pending.get('worker_pid') is not None or pending.get('launcher_pid') is not None)):
            raise RuntimeError('Current-target reservation has no known owner; no retirement allowed')
        if not same_target and process_identity(pending['pid']) is not None:
            raise RuntimeError('Old target is live or its PID was reused; no retirement allowed')
        status_raw=status.read_bytes() if status.exists() else None
        observed=json.loads(status_raw) if status_raw is not None else None
        if observed is not None:
            if (observed.get('startup_token')!=pending['startup_token']
                    or observed.get('session_file')!=str(session.resolve())
                    or (observed.get('pid'),observed.get('process_start_time'))!=(pending['pid'],pending['process_start_time'])):
                raise RuntimeError('Status does not identify this reserved attempt; preserving it')
            _require_absent_worker(observed)
        if pending.get('worker_pid') is not None:_require_absent_worker(pending)
        if pending.get('launcher_pid') is not None:_require_absent_launcher(pending)
        workers=observe_session_workers(session)
        if workers:
            raise RuntimeError('A same-session recovery worker or launcher remains live; no retirement allowed')
        _assert_current(session,expected)
        if not same_target and process_identity(pending['pid']) is not None:
            raise RuntimeError('Old target PID changed during observation; no retirement allowed')
        if status_raw is None and status.exists():
            raise RuntimeError('Recovery status appeared during observation; preserving the reservation')
        destination=_archive_pending(directory,path,raw,status if observed is not None else None,status_raw)
        return {'retired':True,'reservation_archive':str(destination),'worker_launched':False,
                'session_file':str(session.resolve()),'old_pid':pending['pid'],
                'old_process_start_time':pending['process_start_time'],
                'current_pid':expected['pid'],'same_session_workers_observed':0}

def matching_settings(previous,expected,follow_native=False):
    if not previous or not expected:return False
    if not follow_native:return previous==expected
    # Only a native interval can change in-place. Scope changes still require
    # stopping the verified old worker rather than creating a second worker.
    try:
        interval=float(previous['interval_seconds'])
        return (math.isfinite(interval) and interval>0 and
                {k:v for k,v in previous.items() if k!='interval_seconds'}==
                {k:v for k,v in expected.items() if k!='interval_seconds'})
    except (KeyError,TypeError,ValueError):return False

def worker_identity(pid):
    try:
        handle=win32api.OpenProcess(win32con.SYNCHRONIZE|win32con.PROCESS_QUERY_INFORMATION|win32con.PROCESS_VM_READ,False,int(pid))
    except win32api.error as exc:
        if exc.winerror in (87,1168):return None
        raise
    try:
        if win32event.WaitForSingleObject(handle,0)!=win32con.WAIT_TIMEOUT:return None
        return (str(Path(win32process.GetModuleFileNameEx(handle,0)).resolve()).casefold(),
                win32process.GetProcessTimes(handle)['CreationTime'].isoformat())
    finally:handle.Close()

def recovery_worker_error(pid,worker):
    """Observe the connected worker without launching or reconnecting anything."""
    try:
        status=json.loads(Path(worker['status_file']).read_text(encoding='utf-8'))
        if (status['worker_pid']!=worker['worker_pid'] or status['pid']!=int(pid)
                or status['worker_start_time']!=worker['worker_start_time']
                or status['process_start_time']!=worker['process_start_time']):
            return 'Recovery worker status identity changed; monitoring is unverified'
        if process_identity(int(pid))!=status['process_start_time']:
            return 'Recovery target exited or its process identity changed'
        if status['status'] in ('failed','stopped'):
            return 'Recovery monitor '+status['status']+': '+str(status.get('error',status.get('reason','no reason recorded')))
        expected=(str(Path(sys._base_executable).resolve()).casefold(),status['worker_start_time'])
        if worker_identity(status['worker_pid'])!=expected:
            return 'Recovery worker exited or its process identity changed'
        follows=bool(worker.get('policy') and worker['policy'].get('source')=='solidworks'
                     and status.get('follow_native_preferences'))
        if worker.get('policy') and worker['policy'].get('source')=='solidworks' and not follows:
            return 'Recovery worker does not follow native preferences; stop the old worker before reconnecting'
        if not matching_settings(status.get('settings'),worker.get('settings'),follows):
            return 'Recovery worker settings changed or cannot be verified'
        if status.get('unprotected_documents'):
            return 'Recovery monitor has unsupported dirty documents; inspect unprotected_documents in its status file'
        return None
    except Exception as exc:
        return f'Recovery monitor health could not be verified: {exc}'

def ensure_recovery_worker(pid,app=None):
    mode=os.environ.get('SOLIDWORKS_RECOVERY_MONITOR','auto')
    if mode=='0':return None
    if mode not in ('auto','1'):raise ValueError('Recovery monitor must be auto, 1 or 0')
    policy=None
    if mode=='auto':
        if app is None:return None  # Legacy direct helper callers have no CAD binding.
        from .recovery_policy import automatic_policy
        policy=automatic_policy(app,pid,os.environ)
        if not policy['enabled']:return None
    session=Path(os.environ.get('SOLIDWORKS_SESSION_FILE',''))
    directory=Path(policy['directory'] if policy else os.environ.get('SOLIDWORKS_RECOVERY_DIRECTORY',''))
    if not session.is_absolute() or not directory.is_absolute():
        raise ValueError('Recovery monitor requires absolute session and private recovery paths')
    interval=policy['settings']['interval_seconds'] if policy else float(os.environ.get('SOLIDWORKS_RECOVERY_INTERVAL','60'))
    if not math.isfinite(interval) or interval<=0:raise ValueError('Recovery interval must be positive and finite')
    settings=policy['settings'] if policy else recovery_settings(interval)
    status=directory/'monitor.json';marker=directory/'requested.stop'
    validate_status_path(directory,status,session)
    expected=json.loads(session.read_text(encoding='utf-8'))
    if int(expected['pid'])!=int(pid) or process_identity(int(pid))!=expected['start_time']:
        raise RuntimeError('Recovery session does not own the connected process')
    # Separate launch mutex: the worker holds the regular session monitor mutex.
    with monitor_lock(str(session)+'.worker-launch'):
        pending_path=directory/'worker-startup.json'
        pending=json.loads(pending_path.read_text(encoding='utf-8')) if pending_path.exists() else None
        if pending:
            _,pending=_read_pending(pending_path,session)
            observed=json.loads(status.read_text(encoding='utf-8')) if status.exists() else None
            same_target=(pending['pid'],pending['process_start_time'])==(int(pid),expected['start_time'])
            confirmed=observed and observed.get('startup_token')==pending['startup_token']
            if not same_target or not confirmed:
                terminal_claim=(pending.get('protocol_version')==2 and
                    (pending.get('worker_pid') or pending.get('launcher_pid')
                     or pending.get('launch_state')=='failed_before_process_creation'))
                if not terminal_claim and not confirmed:
                    prefix='' if same_target else 'Recovery startup reservation identity mismatch. '
                    raise RuntimeError(prefix+_unconfirmed_message(session,directory))
                _retire_terminal_pending(session,directory,expected)
                pending=None
        if status.exists():
            previous=json.loads(status.read_text(encoding='utf-8'))
            live=worker_identity(previous['worker_pid'])
            if live:
                if (live!=(str(Path(sys._base_executable).resolve()).casefold(),previous['worker_start_time'])
                        or previous['pid']!=int(pid) or previous['process_start_time']!=expected['start_time']):
                    raise RuntimeError('Existing recovery worker identity mismatch; refusing a duplicate')
                if previous['status'] in ('failed','stopped'):
                    raise RuntimeError('Existing recovery worker is finishing shutdown; no replacement was launched')
                if policy and not previous.get('follow_native_preferences'):
                    raise RuntimeError('Existing recovery worker does not follow native preferences; stop that worker before reconnecting')
                if not policy and previous.get('follow_native_preferences'):
                    raise RuntimeError('Existing recovery worker follows native preferences; stop that worker before switching to forced mode')
                follows=bool(policy and previous.get('follow_native_preferences'))
                if not matching_settings(previous.get('settings'),settings,follows):
                    raise RuntimeError('Existing recovery worker settings differ or are unverified; stop that worker before applying new settings')
                if pending:pending_path.unlink()
                return {'worker_pid':previous['worker_pid'],'worker_start_time':previous['worker_start_time'],
                        'process_start_time':expected['start_time'],'settings':settings,'status_file':str(status),'reused':True,'policy':policy}
            if pending:
                # Matching worker-written status plus its absent handle proves
                # this reserved attempt is terminal, unlike a polling timeout.
                _retire_terminal_pending(session,directory,expected)
                pending=None
        if marker.exists():raise RuntimeError('Recovery stop marker exists; monitor remains stopped')
        root=Path(__file__).resolve().parents[1]
        token=uuid.uuid4().hex
        arguments=['-m','solidworks_mcp.recovery_monitor','--session-file',str(session),
                   '--directory',str(directory),'--status-file',str(status),'--interval',str(interval),
                   '--stop-file',str(marker),'--startup-token',token,
                   '--expected-pid',str(pid),'--expected-start-time',expected['start_time'],
                   '--settings-json',json.dumps(settings)]
        if policy:arguments.append('--follow-native-preferences')
        reservation={'kind':'recovery_worker_startup','protocol_version':2,'pid':int(pid),
                     'process_start_time':expected['start_time'],'session_file':str(session.resolve()),
                     'startup_token':token,'launch_state':'reserved'}
        # The short monitor lock prevents a delayed child from claiming an old
        # token while this new attempt is published. Release it before launch.
        with monitor_lock(session):
            _assert_current(session,expected)
            if status.exists():
                # The prior dead worker was already verified above. Preserve its
                # status before the new child's first status write replaces it.
                prior=json.loads(status.read_text(encoding='utf-8'))
                _require_absent_worker(prior)
                archive=_archive_directory(directory)
                os.replace(status,archive/(uuid.uuid4().hex+'-monitor.json'))
            write_state(pending_path,reservation)
        child_created=False
        def before_resume(handle,launcher_pid):
            nonlocal child_created
            child_created=True
            reservation.update(launcher_pid=int(launcher_pid),
                launcher_start_time=win32process.GetProcessTimes(handle)['CreationTime'].isoformat(),
                # CreateProcessW was given this exact executable. Its loader
                # may not have initialized a module list while still suspended.
                launcher_executable=str(Path(sys.executable).resolve()).casefold(),
                launch_state='created_suspended')
            write_state(pending_path,reservation)
        try:
            worker=start_desktop_process(sys.executable,root,arguments,before_resume=before_resume)
        except Exception as exc:
            # The launcher invokes before_resume before any child code can run.
            # If it never invoked that callback, there is no unknown real worker.
            if not child_created:
                reservation.update(launch_state='failed_before_process_creation',launch_error=str(exc))
                write_state(pending_path,reservation)
            raise
        # Require the actual child's status before reporting successful startup.
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if status.exists():
                current=json.loads(status.read_text(encoding='utf-8'))
                if current.get('startup_token')==token:
                    actual=current['worker_pid']
                    if worker_identity(actual)!=(str(Path(sys._base_executable).resolve()).casefold(),current['worker_start_time']):
                        raise RuntimeError('Recovery worker startup identity mismatch')
                    if current.get('pid')!=int(pid) or current.get('process_start_time')!=expected['start_time']:
                        raise RuntimeError('Recovery worker startup target mismatch')
                    if current['status']=='failed':raise RuntimeError(current.get('error','Recovery worker failed'))
                    if current['status']=='stopped':raise RuntimeError('Recovery worker stopped during startup')
                    if current.get('settings')!=settings:raise RuntimeError('Recovery worker startup settings mismatch')
                    _assert_current(session,expected)
                    pending_path.unlink()
                    return {'worker_pid':actual,'worker_start_time':current['worker_start_time'],
                            'process_start_time':expected['start_time'],'settings':settings,'status_file':str(status),'reused':False,'policy':policy}
            if worker_identity(worker) is None:raise RuntimeError('Recovery worker exited before startup confirmation')
            time.sleep(0.1)
        raise RuntimeError(f'Recovery worker {worker} startup observation timed out; do not launch a replacement')


def main():
    parser=argparse.ArgumentParser(description='Safely retire an old same-session recovery startup; never operates CAD')
    parser.add_argument('--retire-stale-startup',action='store_true',required=True)
    parser.add_argument('--session-file',type=Path,required=True)
    parser.add_argument('--directory',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(retire_stale_startup(args.session_file,args.directory),indent=2))

if __name__=='__main__':main()
