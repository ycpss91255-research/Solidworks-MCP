"""Opt-in MCP connection hook for one persistent recovery worker per session."""
import json,math,os,sys,time,uuid
from pathlib import Path
import win32api,win32con,win32event,win32process
from .automation.managed_session import process_identity,write_state
from .recovery_monitor import monitor_lock,validate_status_path
from .desktop_process import start_desktop_process
from .recovery_settings import recovery_settings

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
        if not worker.get('settings') or status.get('settings')!=worker['settings']:
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
            if (pending.get('kind')!='recovery_worker_startup' or pending.get('pid')!=int(pid)
                    or pending.get('process_start_time')!=expected['start_time']
                    or pending.get('session_file')!=str(session.resolve())):
                raise RuntimeError('Recovery startup reservation identity mismatch; refusing a duplicate')
            observed=json.loads(status.read_text(encoding='utf-8')) if status.exists() else None
            if not observed or observed.get('startup_token')!=pending['startup_token']:
                # A venv launcher's exit does not prove its real worker exited.
                # Keep the reservation until that worker's own status identifies it.
                raise RuntimeError('Recovery startup remains unconfirmed; no replacement was launched')
        if status.exists():
            previous=json.loads(status.read_text(encoding='utf-8'))
            live=worker_identity(previous['worker_pid'])
            if live:
                if (live!=(str(Path(sys._base_executable).resolve()).casefold(),previous['worker_start_time'])
                        or previous['pid']!=int(pid) or previous['process_start_time']!=expected['start_time']):
                    raise RuntimeError('Existing recovery worker identity mismatch; refusing a duplicate')
                if previous['status'] in ('failed','stopped'):
                    raise RuntimeError('Existing recovery worker is finishing shutdown; no replacement was launched')
                if previous.get('settings')!=settings:
                    raise RuntimeError('Existing recovery worker settings differ or are unverified; stop that worker before applying new settings')
                if pending:pending_path.unlink()
                return {'worker_pid':previous['worker_pid'],'worker_start_time':previous['worker_start_time'],
                        'process_start_time':expected['start_time'],'settings':settings,'status_file':str(status),'reused':True,'policy':policy}
            if pending:
                # Matching worker-written status plus its absent handle proves
                # this reserved attempt is terminal, unlike a polling timeout.
                pending_path.unlink()
        if marker.exists():raise RuntimeError('Recovery stop marker exists; monitor remains stopped')
        root=Path(__file__).resolve().parents[1]
        token=uuid.uuid4().hex
        arguments=['-m','solidworks_mcp.recovery_monitor','--session-file',str(session),
                   '--directory',str(directory),'--status-file',str(status),'--interval',str(interval),
                   '--stop-file',str(marker),'--startup-token',token,
                   '--settings-json',json.dumps(settings)]
        write_state(pending_path,{'kind':'recovery_worker_startup','pid':int(pid),
                    'process_start_time':expected['start_time'],'session_file':str(session.resolve()),
                    'startup_token':token})
        worker=start_desktop_process(sys.executable,root,arguments)
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
                    pending_path.unlink()
                    return {'worker_pid':actual,'worker_start_time':current['worker_start_time'],
                            'process_start_time':expected['start_time'],'settings':settings,'status_file':str(status),'reused':False,'policy':policy}
            if worker_identity(worker) is None:raise RuntimeError('Recovery worker exited before startup confirmation')
            time.sleep(0.1)
        raise RuntimeError(f'Recovery worker {worker} startup observation timed out; do not launch a replacement')
