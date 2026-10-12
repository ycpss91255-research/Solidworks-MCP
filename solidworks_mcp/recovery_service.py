"""Opt-in MCP connection hook for one persistent recovery worker per session."""
import json,math,os,sys,time
from pathlib import Path
import win32api,win32con,win32event,win32process
from .automation.managed_session import process_identity
from .recovery_monitor import monitor_lock,validate_status_path
from .desktop_process import start_desktop_process

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

def ensure_recovery_worker(pid):
    if os.environ.get('SOLIDWORKS_RECOVERY_MONITOR')!='1':return None
    session=Path(os.environ.get('SOLIDWORKS_SESSION_FILE',''))
    directory=Path(os.environ.get('SOLIDWORKS_RECOVERY_DIRECTORY',''))
    if not session.is_absolute() or not directory.is_absolute():
        raise ValueError('Recovery monitor requires absolute session and private recovery paths')
    interval=float(os.environ.get('SOLIDWORKS_RECOVERY_INTERVAL','60'))
    if not math.isfinite(interval) or interval<=0:raise ValueError('Recovery interval must be positive and finite')
    status=directory/'monitor.json';marker=directory/'requested.stop'
    validate_status_path(directory,status,session)
    expected=json.loads(session.read_text(encoding='utf-8'))
    if int(expected['pid'])!=int(pid) or process_identity(int(pid))!=expected['start_time']:
        raise RuntimeError('Recovery session does not own the connected process')
    # Separate launch mutex: the worker holds the regular session monitor mutex.
    with monitor_lock(str(session)+'.worker-launch'):
        if status.exists():
            previous=json.loads(status.read_text(encoding='utf-8'))
            live=worker_identity(previous['worker_pid'])
            if live:
                if (live!=(str(Path(sys.executable).resolve()).casefold(),previous['worker_start_time'])
                        or previous['pid']!=int(pid) or previous['process_start_time']!=expected['start_time']):
                    raise RuntimeError('Existing recovery worker identity mismatch; refusing a duplicate')
                return {'worker_pid':previous['worker_pid'],'status_file':str(status),'reused':True}
        if marker.exists():raise RuntimeError('Recovery stop marker exists; monitor remains stopped')
        root=Path(__file__).resolve().parents[1]
        arguments=['-m','solidworks_mcp.recovery_monitor','--session-file',str(session),
                   '--directory',str(directory),'--status-file',str(status),'--interval',str(interval),
                   '--stop-file',str(marker)]
        worker=start_desktop_process(sys.executable,root,arguments)
        # Require the actual child's status before reporting successful startup.
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if status.exists():
                current=json.loads(status.read_text(encoding='utf-8'))
                if current.get('worker_pid')==worker:
                    if current['status']=='failed':raise RuntimeError(current.get('error','Recovery worker failed'))
                    return {'worker_pid':worker,'status_file':str(status),'reused':False}
            if worker_identity(worker) is None:raise RuntimeError('Recovery worker exited before startup confirmation')
            time.sleep(0.1)
        raise RuntimeError(f'Recovery worker {worker} startup observation timed out; do not launch a replacement')
