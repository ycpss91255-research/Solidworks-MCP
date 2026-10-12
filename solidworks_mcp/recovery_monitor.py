"""Opt-in foreground part monitor; never launches or retargets SolidWorks."""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import argparse,hashlib,json,math,time,os
import win32api,win32con,win32event,win32gui,win32process
from .automation.managed_session import process_identity,write_state
from .recovery_snapshot import get0

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
    def connect(self):return self.automation.connect()
    def probe(self):
        if not self.automation.is_connected:raise RuntimeError('Configured MCP connection was lost')
        from win32com.client import gencache
        raw=self.automation.app
        revision=get0(raw,'RevisionNumber')
        module=gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,int(str(revision).split('.')[0]),0)
        app=module.ISldWorks(raw._oleobj_)
        if int(get0(app,'GetProcessID'))!=self.pid:raise RuntimeError('Application PID mismatch')
        if app.CommandInProgress:return {'state':'busy'}
        doc=app.ActiveDoc
        if doc is None:return {'state':'no_document'}
        doc=module.IModelDoc2(doc._oleobj_)
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
    def snapshot(self):return self.automation.create_recovery_snapshot(str(self.directory))
    def close(self):self.automation.disconnect()

def run_monitor(pid,identity,directory,status_file,interval,backend,
                max_ticks=None,stop=None,identity_reader=process_identity,
                dialog_reader=visible_dialog,clock=time.monotonic,sleep=time.sleep,session_file=None,startup_token=None):
    """Sequential ticks. A connection/save error is terminal, never retried."""
    if pid<=0 or not identity:raise ValueError('A PID and process creation identity are required')
    if not math.isfinite(interval) or interval<=0:raise ValueError('Interval must be finite and positive')
    if max_ticks is not None and max_ticks<=0:raise ValueError('max_ticks must be positive')
    directory=Path(directory);status_file=Path(status_file)
    validate_status_path(directory,status_file,session_file)
    state={'kind':'part_recovery_monitor','pid':pid,'process_start_time':identity,'worker_pid':__import__('os').getpid(),
           'worker_start_time':win32process.GetProcessTimes(win32api.GetCurrentProcess())['CreationTime'].isoformat(),
           'directory':str(directory),'interval_seconds':interval,'status':'starting','ticks':0,'snapshots':0}
    if session_file:state['session_file']=str(Path(session_file).resolve())
    if startup_token:state['startup_token']=startup_token
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
                if not connected:
                    result=backend.connect()
                    if not result['success']:raise RuntimeError(result.get('message','Target connection failed'))
                    connected=True
                probe=backend.probe()
                if probe['state']=='dirty':
                    record('snapshot_in_progress')
                    result=backend.snapshot()
                    if not result['success']:raise RuntimeError(result.get('message','Recovery snapshot failed'))
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
        record('failed',error=str(exc))
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
    parser.add_argument('--stop-file',type=Path,help='Private .stop marker; exits at the next scheduler check')
    args=parser.parse_args()
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
    target=json.loads(args.session_file.read_text(encoding='utf-8'))
    pid=int(target['pid']);identity=target['start_time']
    if process_identity(pid)!=identity:raise RuntimeError('Recorded target has exited or changed; no CAD process was launched')
    with monitor_lock(args.session_file):
        backend=CadBackend(pid,args.directory)
        def current_identity(requested):
            latest=json.loads(args.session_file.read_text(encoding='utf-8'))
            if int(latest['pid'])!=pid or latest['start_time']!=identity:
                raise RuntimeError('This session changed its target; monitor will not retarget')
            return process_identity(requested)
        result=run_monitor(pid,identity,args.directory,args.status_file,args.interval,backend,args.max_ticks,
                           identity_reader=current_identity,session_file=args.session_file,startup_token=args.startup_token,
                           stop=(lambda:args.stop_file.exists()) if args.stop_file else None)
        print(json.dumps(result,indent=2))
        if result['status']=='failed':raise SystemExit(1)

if __name__=='__main__':main()
