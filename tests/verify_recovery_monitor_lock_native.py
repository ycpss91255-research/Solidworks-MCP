"""Windows mutex ownership test with Python helpers; never invokes CAD."""
import json,subprocess,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solidworks_mcp.recovery_monitor import monitor_lock
if '--child' in sys.argv:
    session,ready,release=sys.argv[2:5]
    with monitor_lock(session):
        Path(ready).write_text('acquired')
        if release!='once':
            deadline=time.monotonic()+15
            while not Path(release).exists() and time.monotonic()<deadline:time.sleep(0.01)
            if not Path(release).exists():raise RuntimeError('Fixture timeout')
else:
    script=str(Path(__file__).resolve())
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);session=root/'session.json';ready=root/'ready';release=root/'release'
        args=[sys.executable,script,'--child',str(session),str(ready),str(release)]
        holder=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                creationflags=0x08000000)
        try:
            deadline=time.monotonic()+10
            while not ready.exists() and time.monotonic()<deadline and holder.poll() is None:time.sleep(0.01)
            assert ready.exists(),'Owner did not acquire mutex'
            duplicate=subprocess.run([sys.executable,script,'--child',str(session),str(root/'duplicate'),'once'],capture_output=True,text=True,timeout=10,creationflags=0x08000000)
            assert duplicate.returncode!=0 and 'already has' in duplicate.stderr
            assert not (root/'duplicate').exists()
            independent=subprocess.run([sys.executable,script,'--child',str(root/'another-session.json'),str(root/'independent'),'once'],capture_output=True,text=True,timeout=10,creationflags=0x08000000)
            assert independent.returncode==0,independent.stderr
            release.write_text('stop')
            holder.communicate(timeout=10);assert holder.returncode==0
            restarted=subprocess.run([sys.executable,script,'--child',str(session),str(root/'restarted'),'once'],capture_output=True,text=True,timeout=10,creationflags=0x08000000)
            assert restarted.returncode==0,restarted.stderr
            print(json.dumps({'passed':True,'duplicate_session_refused':True,'independent_session_allowed':True,'released_lock_reusable':True,'solidworks_touched':False}))
        finally:
            if holder.poll() is None:
                release.write_text('stop')
                try:holder.communicate(timeout=5)
                except subprocess.TimeoutExpired:holder.terminate();holder.communicate(timeout=5)
