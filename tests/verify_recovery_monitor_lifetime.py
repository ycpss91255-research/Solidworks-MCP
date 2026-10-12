"""Run a real scheduler with a fake backend across MCP-style job cleanup."""
import json,subprocess,sys,tempfile,time
from pathlib import Path
import win32api,win32con,win32event,win32job
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    directory=Path(folder);status=directory/'monitor.json';stop=directory/'stop'
    worker=directory/'worker.py';server_script=directory/'server.py';gate=directory/'gate';created=directory/'child.json'
    worker.write_text(f"""import sys
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
from solidworks_mcp.recovery_monitor import run_monitor
class FakeBackend:
    def connect(self):return {{'success':True}}
    def probe(self):return {{'state':'dirty'}}
    def snapshot(self):return {{'success':True,'data':{{'status':'complete','pid':123,'process_start_time':'fixture'}}}}
    def close(self):pass
run_monitor(123,'fixture',Path({str(directory)!r}),Path({str(status)!r}),0.1,FakeBackend(),
    identity_reader=lambda pid:'fixture',dialog_reader=lambda pid:False,stop=lambda:Path({str(stop)!r}).exists())
""",encoding='utf-8')
    server_script.write_text(f"""import sys,time,json
from pathlib import Path
sys.path.insert(0,{str(ROOT)!r})
from solidworks_mcp.desktop_process import start_desktop_process
while not Path({str(gate)!r}).exists():time.sleep(0.01)
pid=start_desktop_process({sys._base_executable!r},Path({str(ROOT)!r}),[{str(worker)!r}])
Path({str(created)!r}).write_text(json.dumps({{'pid':pid}}))
time.sleep(30)
""",encoding='utf-8')
    job=win32job.CreateJobObject(None,'')
    info=win32job.QueryInformationJobObject(job,win32job.JobObjectExtendedLimitInformation)
    info['BasicLimitInformation']['LimitFlags']|=win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    win32job.SetInformationJobObject(job,win32job.JobObjectExtendedLimitInformation,info)
    server=subprocess.Popen([sys._base_executable,str(server_script)],creationflags=0x08000000)
    child=None
    try:
        handle=win32api.OpenProcess(0x100|1,False,server.pid)
        try:win32job.AssignProcessToJobObject(job,handle)
        finally:handle.Close()
        gate.touch();deadline=time.monotonic()+15
        while not status.exists() and time.monotonic()<deadline:time.sleep(0.05)
        assert status.exists(),'Fixture monitor did not start'
        child_pid=json.loads(created.read_text())['pid']
        child=win32api.OpenProcess(win32con.SYNCHRONIZE|win32con.PROCESS_TERMINATE,False,child_pid)
        before=json.loads(status.read_text())['snapshots']
        job.Close();job=None;server.wait(timeout=5)
        assert win32event.WaitForSingleObject(child,0)==win32con.WAIT_TIMEOUT
        deadline=time.monotonic()+5
        after=before
        while after<=before and time.monotonic()<deadline:
            time.sleep(0.05);after=json.loads(status.read_text())['snapshots']
        assert after>before,'Scheduler did not continue after parent job closed'
        stop.touch();assert win32event.WaitForSingleObject(child,5000)==0
        assert json.loads(status.read_text())['status']=='stopped'
        print(json.dumps({'passed':True,'scheduler_survived_parent_cleanup':True,
                          'ticks_continued':True,'explicit_stop_exited_worker':True,'backend':'fake','solidworks_touched':False}))
    finally:
        stop.touch()
        if child:
            if win32event.WaitForSingleObject(child,5000)!=0:win32api.TerminateProcess(child,1)
            child.Close()
        if job:job.Close()
        if server.poll() is None:server.terminate()
        server.wait(timeout=5)
