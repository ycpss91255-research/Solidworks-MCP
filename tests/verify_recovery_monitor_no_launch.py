"""Expired target with inherited auto-launch must not start CAD."""
import json,os,subprocess,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from launch_solidworks import running_pids
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    temporary=Path(folder)
    session=temporary/'session.json'
    session.write_text(json.dumps({'pid':2147483646,'start_time':'expired'}))
    environment=dict(os.environ,SOLIDWORKS_AUTO_LAUNCH='1',SOLIDWORKS_SESSION_FILE=str(session))
    before=set(running_pids())
    result=subprocess.run([sys.executable,'-m','solidworks_mcp.recovery_monitor',
        '--session-file',str(session),'--directory',str(temporary/'recovery'),
        '--status-file',str(temporary/'recovery/status.json'),'--interval','1','--max-ticks','1'],
        cwd=root,env=environment,capture_output=True,text=True,timeout=15,creationflags=0x08000000)
    assert result.returncode!=0
    assert 'no CAD process was launched' in result.stderr
    assert set(running_pids())==before
    assert not (temporary/'recovery').exists()
    assert json.loads(session.read_text())['pid']==2147483646
    print(json.dumps({'passed':True,'inherited_auto_launch_ignored':True,'solidworks_pids_unchanged':sorted(before),'session_unchanged':True}))
