"""Opt-in foreground part monitor; never launches or retargets SolidWorks."""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import argparse,hashlib,json,math,time,os,traceback
import win32api,win32con,win32event,win32gui,win32process
from .automation.managed_session import process_identity,write_state
from .recovery_snapshot import get0
from .recovery_settings import recovery_settings

def validate_status_path(directory,status_file,session_file=None):
    directory=Path(directory);status_file=Path(status_file)
    if not directory.is_absolute() or not status_file.is_absolute():raise ValueError('Monitor paths must be absolute')
    if status_file.suffix.casefold()!='.json' or not status_file.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Monitor status must be a JSON file inside its private recovery directory')
    if status_file.exists():
        existing=json.loads(status_file.read_text(encoding='utf-8'))
        if existing.get('kind')!='part_recovery_monitor':raise ValueError('Refusing to overwrite an unrelated status file')
        if session_file and existing.get('session_file')!=str(Path(session_file).resolve()):
            raise ValueError('Refusing to overwrite another session monitor status')

@contextmanager
def monitor_lock(session_file):
    key=hashlib.sha256(str(Path(session_file).resolve()).casefold().encode()).hexdigest()
    mutex=win32event.CreateMutex(None,False,'Local\\SWMCPRecovery_'+key)
    acquired=False
    try:
        result=win32event.WaitForSingleObject(mutex,0)
        acquired=result in (win32con.WAIT_OBJECT_0,win32con.WAIT_ABANDONED)
        if not acquired:raise RuntimeError('This session already has a recovery monitor')
        yield
    finally:
        if acquired:win32event.ReleaseMutex(mutex)
        mutex.Close()

@contextmanager
def worker_startup(session_file,directory,expected_pid,expected_start_time,startup_token):
    """Claim a reserved attempt before any CAD call; hold its monitor lock.

    The parent owns the separate launch mutex while waiting for confirmation.
    Never acquire that mutex here: retirement takes launch then monitor, while
    this worker takes only monitor and keeps it throughout its lifetime.
    """
    session_file=Path(session_file);directory=Path(directory)
    if not session_file.is_absolute() or not directory.is_absolute():
        raise ValueError('Worker startup paths must be absolute')
    if int(expected_pid)<=0 or not expected_start_time or not startup_token:
        raise ValueError('Worker startup requires an explicit target identity and token')
    with monitor_lock(session_file):
        pending_path=directory/'worker-startup.json'
        pending=json.loads(pending_path.read_text(encoding='utf-8'))
        target=json.loads(session_file.read_text(encoding='utf-8'))
        if (pending.get('kind')!='recovery_worker_startup' or pending.get('protocol_version')!=2
                or pending.get('session_file')!=str(session_file.resolve())
                or pending.get('startup_token')!=startup_token):
            raise RuntimeError('Worker startup reservation/token no longer belongs to this attempt')
        identity=(int(expected_pid),expected_start_time)
        if (identity!=(pending.get('pid'),pending.get('process_start_time'))
                or identity!=(target.get('pid'),target.get('start_time'))
                or process_identity(int(expected_pid))!=expected_start_time):
            raise RuntimeError('Worker startup target identity changed; no retargeting or CAD calls allowed')
        if pending.get('worker_pid') is not None:
            raise RuntimeError('Worker startup reservation was already claimed')
        if (directory/'requested.stop').exists():
            raise RuntimeError('Recovery stop marker exists; worker remains stopped')
        handle=win32api.GetCurrentProcess()
        pending.update(worker_pid=os.getpid(),
            worker_start_time=win32process.GetProcessTimes(handle)['CreationTime'].isoformat(),
            worker_executable=str(Path(win32process.GetModuleFileNameEx(handle,0)).resolve()).casefold(),
            launch_state='claimed')
        write_state(pending_path,pending)
        yield target

def visible_dialog(pid):
    windows=[]
    def visit(hwnd,_):
        try:
            if (win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd)=='#32770'
                    and win32process.GetWindowThreadProcessId(hwnd)[1]==pid):windows.append(hwnd)
        except win32gui.error:pass
    win32gui.EnumWindows(visit,None)
    return bool(windows)

class CadBackend:
    def __init__(self,pid,directory):
        from .automation import SolidWorksAutomation
        self.automation=SolidWorksAutomation()
        self.automation._target_pid=str(pid)
        self.automation._configured_target=str(pid)
        self.automation._auto_launch=False
        self.automation._recovery_startup_enabled=False
        self.pid=pid;self.directory=directory
        self.assembly_enabled=os.environ.get('SOLIDWORKS_RECOVERY_ASSEMBLIES')=='1'
        self.drawing_enabled=os.environ.get('SOLIDWORKS_RECOVERY_DRAWINGS')=='1'
        self.all_documents=os.environ.get('SOLIDWORKS_RECOVERY_ALL_DOCUMENTS')=='1'
        self.background_activation=os.environ.get('SOLIDWORKS_RECOVERY_BACKGROUND_ACTIVATION')=='1'
    def connect(self):return self.automation.connect()
    def native_fault_result(self):return self.automation.native_fault_result()
    def record_native_failure(self,error):return self.automation.record_native_failure(error)
    def probe(self):
        if not self.automation.is_connected:raise RuntimeError('Configured MCP connection was lost')
        from win32com.client import gencache
        raw=self.automation.app
        revision=get0(raw,'RevisionNumber')
        module=gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,int(str(revision).split('.')[0]),0)
        app=module.ISldWorks(raw._oleobj_)
        if int(get0(app,'GetProcessID'))!=self.pid:raise RuntimeError('Application PID mismatch')
        if app.CommandInProgress:return {'state':'busy'}
        if self.all_documents:
            self._batch_app=app;self._batch_adapter=lambda d:module.IModelDoc2(d._oleobj_)
            self._batch_documents=[];self._unprotected=[]
            for raw_doc in get0(app,'GetDocuments') or ():
                model=self._batch_adapter(raw_doc);probe=self._probe_document(model,module)
                if probe['state']=='dirty':self._batch_documents.append(raw_doc)
                elif probe['state']=='unsupported_document' and bool(get0(model,'GetSaveFlag')):
                    self._unprotected.append({'path':get0(model,'GetPathName'),'title':get0(model,'GetTitle')})
            return {'state':'dirty' if self._batch_documents else 'clean','unprotected_documents':self._unprotected}
        doc=app.ActiveDoc
        if doc is None:return {'state':'no_document'}
        doc=module.IModelDoc2(doc._oleobj_)
        return self._probe_document(doc,module)
    def _probe_document(self,doc,module):
        kind=int(get0(doc,'GetType'))
        dirty=bool(get0(doc,'GetSaveFlag'))
        def assembly_children_dirty(model):
            assembly=module.IAssemblyDoc(model._oleobj_)
            for raw_component in assembly.GetComponents(False) or ():
                component=module.IComponent2(raw_component._oleobj_)
                child=get0(component,'GetModelDoc2')
                if child is not None and bool(get0(module.IModelDoc2(child._oleobj_),'GetSaveFlag')):
                    return True
            return False
        if kind==2 and self.assembly_enabled:
            dirty=dirty or assembly_children_dirty(doc)
            return {'state':'dirty' if dirty else 'clean'}
        if kind==3 and self.drawing_enabled:
            drawing=module.IDrawingDoc(doc._oleobj_)
            raw_view=get0(drawing,'GetFirstView')
            while raw_view is not None:
                view=module.IView(raw_view._oleobj_)
                model=get0(view,'ReferencedDocument')
                if model is not None:
                    model=module.IModelDoc2(model._oleobj_)
                    dirty=dirty or bool(get0(model,'GetSaveFlag'))
                    if int(get0(model,'GetType'))==2:dirty=dirty or assembly_children_dirty(model)
                raw_view=get0(view,'GetNextView')
            return {'state':'dirty' if dirty else 'clean'}
        if kind!=1:return {'state':'unsupported_document'}
        return {'state':'dirty' if dirty else 'clean'}
    def snapshot(self):
        if self.all_documents:
            from .recovery_batch import snapshot_documents
            result=snapshot_documents(self._batch_app,self.pid,str(self.directory),self._batch_documents,
                self._batch_adapter,allow_activation=self.background_activation,
                idle=lambda:not self._batch_app.CommandInProgress and not visible_dialog(self.pid))
            result.setdefault('data',{})['unprotected_documents']=self._unprotected
            return result
        return self.automation.create_recovery_snapshot(str(self.directory))
    def close(self):self.automation.disconnect()

def run_monitor(pid,identity,directory,status_file,interval,backend,
                max_ticks=None,stop=None,identity_reader=process_identity,
                dialog_reader=visible_dialog,clock=time.monotonic,sleep=time.sleep,session_file=None,startup_token=None,
                preference_reader=None):
    """Sequential ticks. A connection/save error is terminal, never retried."""
    if pid<=0 or not identity:raise ValueError('A PID and process creation identity are required')
    if not math.isfinite(interval) or interval<=0:raise ValueError('Interval must be finite and positive')
    if max_ticks is not None and max_ticks<=0:raise ValueError('max_ticks must be positive')
    directory=Path(directory);status_file=Path(status_file)
    validate_status_path(directory,status_file,session_file)
    state={'kind':'part_recovery_monitor','pid':pid,'process_start_time':identity,'worker_pid':__import__('os').getpid(),
           'worker_start_time':win32process.GetProcessTimes(win32api.GetCurrentProcess())['CreationTime'].isoformat(),
           'directory':str(directory),'interval_seconds':interval,'settings':recovery_settings(interval),
           'status':'starting','ticks':0,'snapshots':0}
    if session_file:state['session_file']=str(Path(session_file).resolve())
    if startup_token:state['startup_token']=startup_token
    state['follow_native_preferences']=preference_reader is not None
    def record(status,**values):
        state.update(status=status,updated_at=datetime.now(timezone.utc).isoformat(),**values)
        write_state(status_file,state)
    next_tick=clock()
    connected=False
    try:
        record('starting')
        while max_ticks is None or state['ticks']<max_ticks:
            if stop and stop():record('stopped',reason='stop_requested');break
            if identity_reader(pid)!=identity:record('stopped',reason='target_exited_or_identity_changed');break
            remaining=next_tick-clock()
            if remaining>0:
                sleep(min(remaining,1));continue
            state['ticks']+=1
            # Do not invoke COM or dismiss an existing dialog.
            if dialog_reader(pid):record('waiting_dialog')
            else:
                fault_check=getattr(backend,'native_fault_result',None)
                blocked=fault_check() if callable(fault_check) else None
                if isinstance(blocked,dict) and not blocked.get('success'):
                    state['native_fault_block']=blocked.get('data',{})
                    raise RuntimeError(blocked.get('message','Native fault target is blocked'))
                if not connected:
                    result=backend.connect()
                    if not result['success']:raise RuntimeError(result.get('message','Target connection failed'))
                    connected=True
                if preference_reader is not None:
                    policy=preference_reader()
                    state['preferences']=policy['preferences']
                    if not policy['enabled']:
                        # Keep this same session worker idle so re-enabling
                        # native recovery does not require a duplicate worker.
                        record('waiting_preferences_disabled')
                        next_tick=clock()+60
                        continue
                    interval=float(policy['settings']['interval_seconds'])
                    if not math.isfinite(interval) or interval<=0:
                        raise ValueError('Recovery interval must be finite and positive')
                    state['settings']=policy['settings']
                    state['interval_seconds']=interval
                probe=backend.probe()
                if 'unprotected_documents' in probe:state['unprotected_documents']=probe['unprotected_documents']
                if probe['state']=='dirty':
                    record('snapshot_in_progress')
                    result=backend.snapshot()
                    if not result['success']:
                        if result.get('data'):state['last_failed_snapshot']=result['data']
                        raise RuntimeError(result.get('message','Recovery snapshot failed'))
                    snapshot=result.get('data',{})
                    if (snapshot.get('status')!='complete' or snapshot.get('pid')!=pid
                            or snapshot.get('process_start_time')!=identity):
                        raise RuntimeError('Snapshot result is incomplete or belongs to a different process')
                    state['snapshots']+=1
                    record('snapshot_complete',last_snapshot=result['data'])
                else:record('waiting_'+probe['state'])
            # Schedule from completion; never queue overlapping/backlogged saves.
            next_tick=clock()+interval
        else:record('stopped',reason='tick_limit')
    except KeyboardInterrupt:
        record('stopped',reason='keyboard_interrupt')
    except Exception as exc:
        recorder=getattr(backend,'record_native_failure',None)
        fault=recorder(exc) if callable(recorder) else None
        if isinstance(fault,dict):state['native_fault']=fault
        record('failed',error=str(exc),error_traceback=traceback.format_exc())
    finally:
        try:backend.close()
        except Exception as exc:record('failed',error=f'Connection cleanup failed: {exc}')
    return state

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session-file',type=Path,required=True)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--status-file',type=Path,required=True)
    parser.add_argument('--interval',type=float,required=True)
    parser.add_argument('--max-ticks',type=int)
    parser.add_argument('--startup-token',help='Parent/worker startup correlation token')
    parser.add_argument('--expected-pid',type=int,help='Immutable target of the reserved startup attempt')
    parser.add_argument('--expected-start-time',help='Immutable CAD creation time of the startup attempt')
    parser.add_argument('--settings-json',help='Effective scope from the bound session recovery policy')
    parser.add_argument('--follow-native-preferences',action='store_true',help='Read bound CAD preferences before each scheduled save')
    parser.add_argument('--stop-file',type=Path,help='Private .stop marker; exits at the next scheduler check')
    args=parser.parse_args()
    if args.settings_json:
        settings=json.loads(args.settings_json)
        if settings.get('interval_seconds')!=args.interval:parser.error('Recovery settings interval mismatch')
        for name,variable in [('assemblies','ASSEMBLIES'),('drawings','DRAWINGS'),('all_documents','ALL_DOCUMENTS'),('background_activation','BACKGROUND_ACTIVATION')]:
            if type(settings.get(name)) is not bool:parser.error('Invalid recovery scope setting')
            os.environ['SOLIDWORKS_RECOVERY_'+variable]='1' if settings[name] else '0'
    paths=(args.session_file,args.directory,args.status_file)
    if not all(path.is_absolute() for path in paths):parser.error('All paths must be absolute')
    if args.session_file.resolve()==args.status_file.resolve():parser.error('Status must not overwrite the CAD session file')
    validate_status_path(args.directory,args.status_file,args.session_file)
    if args.stop_file:
        if (not args.stop_file.is_absolute() or args.stop_file.suffix.casefold()!='.stop'
                or not args.stop_file.resolve().is_relative_to(args.directory.resolve())
                or args.stop_file.resolve() in (args.session_file.resolve(),args.status_file.resolve())):
            parser.error('Stop marker must be a separate absolute .stop file inside the recovery directory')
    if not math.isfinite(args.interval) or args.interval<=0:parser.error('Interval must be finite and positive')
    if args.max_ticks is not None and args.max_ticks<=0:parser.error('max-ticks must be positive')
    if bool(args.startup_token)!=bool(args.expected_pid and args.expected_start_time):
        parser.error('Reserved startup requires --startup-token, --expected-pid and --expected-start-time together')
    if not args.startup_token and (args.expected_pid is not None or args.expected_start_time is not None):
        parser.error('Expected target requires a reserved startup token')
    target=json.loads(args.session_file.read_text(encoding='utf-8'))
    pid=int(args.expected_pid if args.startup_token else target['pid'])
    identity=args.expected_start_time if args.startup_token else target['start_time']
    if process_identity(pid)!=identity:raise RuntimeError('Recorded target has exited or changed; no CAD process was launched')
    ownership=(worker_startup(args.session_file,args.directory,pid,identity,args.startup_token)
               if args.startup_token else monitor_lock(args.session_file))
    with ownership:
        backend=CadBackend(pid,args.directory)
        def current_identity(requested):
            latest=json.loads(args.session_file.read_text(encoding='utf-8'))
            if int(latest['pid'])!=pid or latest['start_time']!=identity:
                raise RuntimeError('This session changed its target; monitor will not retarget')
            return process_identity(requested)
        def read_preferences():
            from .recovery_policy import automatic_policy
            environment=dict(os.environ,SOLIDWORKS_SESSION_FILE=str(args.session_file),
                             SOLIDWORKS_RECOVERY_DIRECTORY=str(args.directory))
            return automatic_policy(backend.automation.app,pid,environment)
        result=run_monitor(pid,identity,args.directory,args.status_file,args.interval,backend,args.max_ticks,
                           identity_reader=current_identity,session_file=args.session_file,startup_token=args.startup_token,
                           preference_reader=read_preferences if args.follow_native_preferences else None,
                           stop=(lambda:args.stop_file.exists()) if args.stop_file else None)
        print(json.dumps(result,indent=2))
        if result['status']=='failed':raise SystemExit(1)

if __name__=='__main__':main()
