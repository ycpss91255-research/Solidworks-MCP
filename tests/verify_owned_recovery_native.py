"""Root-run native lifecycle/snapshot validation for the fixed private part.

Never launches CAD, changes native preferences, controls UI, edits a model,
closes a document, or terminates a process. It starts only the isolated recovery
Python worker and requests its natural stop. Root creates/edits/reopens the part.
"""
from contextlib import ExitStack
from datetime import datetime, timezone, timedelta
from pathlib import Path
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
LAB = Path('C:/Users/yunchien.chen/mcp/solidworks-mcp-pid-isolation/test-results/remaining-fault-correlation')
OWNER = Path('C:/Users/yunchien.chen/.codex/worktrees/solidworks-recovery/solidworks_data/.codex')
SESSION = OWNER / 'crash-probe-20261014-sensor-part-baseline.json'
WATCH = LAB / 'debug-sensor-part-baseline-v1'
PRIVATE = LAB / 'sensor-private-valid-part-v1'
PART = PRIVATE / 'sensor-valid-part-v1.SLDPRT'
FIXTURE = PRIVATE / 'fixture-resume-response.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): sha.update(block)
    return sha.hexdigest()

async def native_auto_ensure(pid,start_time,environment,report,save,guard):
    """Read native settings and explicitly ensure via isolated PID-bound MCP."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    com_trace=PRIVATE/'recovery-auto-policy-trace.jsonl'
    assert not com_trace.exists()
    watcher=report['watcher']
    code = f'''import json,os
from pathlib import Path
from datetime import datetime
import win32api,win32con,win32event,win32process
from solidworks_mcp.recovery_policy import automatic_policy
from solidworks_mcp.recovery_service import ensure_recovery_worker
from solidworks_mcp.automation.managed_session import process_identity
from solidworks_mcp.native_fault import FaultStore
from solidworks_mcp.recovery_snapshot import get0
watch=Path({str(WATCH)!r}); trace=Path({str(com_trace)!r})
def guard():
 assert win32event.WaitForSingleObject(watcher_handle,0)==win32con.WAIT_TIMEOUT,'Owned native watcher exited during preference call'
 assert process_identity({pid})=={start_time!r}
 assert FaultStore().read({pid},lambda _: {start_time!r}) is None
 assert all(not(watch/n).exists() for n in ('exception.dmp','breakpoint.dmp','result.json','stop.request'))
 for name in ('console.txt','engine.txt'):
  p=watch/name
  if p.exists(): assert not any(line.strip() in ('CAPTURED_OWNED_AV','CAPTURED_OWNED_BREAKPOINT') for line in p.read_text(encoding='utf8',errors='replace').splitlines())
def note(event,member,value=None):
 with trace.open('a',encoding='utf8') as f:
  f.write(json.dumps({{'event':event,'member':member,'value':value}})+'\\n');f.flush();os.fsync(f.fileno())
def call(member,operation):
 guard();note('begin',member)
 try: value=operation();guard()
 except BaseException as e: note('exception',member,str(e));raise
 note('end',member,value);return value
class Preferences:
 def GetProcessID(self): return call('GetProcessID',lambda:get0(sw,'GetProcessID'))
 def GetUserPreferenceToggle(self,n): return call('GetUserPreferenceToggle:'+str(n),lambda:sw.GetUserPreferenceToggle(n))
 def GetUserPreferenceIntegerValue(self,n): return call('GetUserPreferenceIntegerValue:'+str(n),lambda:sw.GetUserPreferenceIntegerValue(n))
watcher_handle=win32api.OpenProcess(win32con.SYNCHRONIZE|win32con.PROCESS_QUERY_INFORMATION|win32con.PROCESS_VM_READ,False,{watcher['pid']})
try:
 assert Path(win32process.GetModuleFileNameEx(watcher_handle,0)).resolve()==Path({watcher['image']!r}).resolve()
 assert abs(win32process.GetProcessTimes(watcher_handle)['CreationTime'].timestamp()-datetime.fromisoformat({watcher['start_time']!r}).timestamp())<.001
 os.environ['SOLIDWORKS_RECOVERY_MONITOR']='auto'
 os.environ.pop('SOLIDWORKS_RECOVERY_INTERVAL',None)
 proxy=Preferences()
 policy=automatic_policy(proxy,{pid},os.environ)
 guard()
 worker=ensure_recovery_worker({pid},app=proxy)
 auto_worker_started=worker is not None
 if not policy['enabled']:
  assert worker is None
  os.environ['SOLIDWORKS_RECOVERY_MONITOR']='1';os.environ['SOLIDWORKS_RECOVERY_INTERVAL']='2'
  worker=ensure_recovery_worker({pid})
 guard()
 effective={{k:os.environ.get(k) for k in ('SOLIDWORKS_RECOVERY_MONITOR','SOLIDWORKS_RECOVERY_INTERVAL','SOLIDWORKS_RECOVERY_DIRECTORY','SOLIDWORKS_RECOVERY_ALL_DOCUMENTS','SOLIDWORKS_RECOVERY_BACKGROUND_ACTIVATION')}}
 print('RECOVERY_NATIVE_RESULT='+json.dumps({{'policy':policy,'auto_worker_started':auto_worker_started,'explicit_control':not policy['enabled'],'worker':worker,'effective_environment':effective}}))
finally: watcher_handle.Close()
'''
    env=dict(os.environ,**environment,PYTHONPATH=str(ROOT))
    env['SOLIDWORKS_RECOVERY_MONITOR']='0'  # connection itself never starts a monitor
    env.pop('SOLIDWORKS_RECOVERY_INTERVAL',None)
    env['SOLIDWORKS_MCP_LOG']=str(PRIVATE/'recovery-auto-mcp-{server_pid}.log')
    params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'solidworks_mcp_server.py')],env=env,cwd=str(ROOT))
    report['auto_mcp_calls']=[];save();guard()
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=60)) as client:
            await client.initialize()
            for name,arguments in (('connect_solidworks',{}),('execute_python',{'code':code})):
                guard();item=await client.call_tool(name,arguments)
                receipt=item.model_dump(mode='json');report['auto_mcp_calls'].append({'tool':name,'response':receipt});save()
                guard();assert not receipt.get('isError')
                text=receipt['content'][0]['text'];assert text.startswith('[SUCCESS]'),text
    lines=[line for line in text.splitlines() if line.startswith('RECOVERY_NATIVE_RESULT=')]
    assert len(lines)==1
    result=json.loads(lines[0].split('=',1)[1])
    assert result['auto_worker_started']==bool(result['policy']['enabled'])
    report['native_auto_policy']=result;save()
    return result['worker']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--start-time', required=True)
    parser.add_argument('--phase', choices=('lifecycle', 'backup'), required=True)
    args = parser.parse_args()
    if sys.flags.optimize: raise RuntimeError('Do not run this verification with Python -O')
    assert ROOT == Path('C:/Users/yunchien.chen/mcp/solidworks-mcp-recovery-reservation-test')
    sys.path.insert(0, str(ROOT)); sys.path.insert(1, str(LAB))
    import win32api, win32con, win32event, win32process
    from solidworks_mcp import recovery_service as service
    from solidworks_mcp.native_fault import FaultStore
    import sensor_case_coordinator_v1 as coordinator
    import evidence_storage
    assert Path(service.__file__).resolve().parent == ROOT / 'solidworks_mcp'
    assert Path(os.environ.get('PYTHONPATH', '')).resolve() == ROOT, 'Set exact isolated PYTHONPATH before running'
    assert Path.cwd().resolve() == ROOT, 'Run from the isolated checkout'
    assert PRIVATE.resolve().parent == LAB.resolve()
    fixture = read(FIXTURE)
    assert fixture['passed'] and fixture['request_success']
    assert (fixture['pid'], fixture['start_time']) == (args.pid, args.start_time)
    facts = fixture['verified_trace']['result']
    assert Path(facts['document']).resolve() == PART.resolve()
    assert facts['external_reference_count'] == 0 and facts['dependencies'] == []
    assert facts['sensor_created'] is False
    baseline = fixture['baseline_artifact']
    assert Path(baseline['path']).resolve() == PART.resolve()
    assert digest(PART) == baseline['sha256'] and PART.stat().st_size == baseline['bytes']
    if args.phase == 'backup':
        previous = read(PRIVATE / 'recovery-lifecycle-response.json')
        assert previous['passed'] and previous['pid'] == args.pid and previous['start_time'] == args.start_time
    external = evidence_storage.require_sandisk()
    backup = external / 'recovery-reservation-native-part-v1' / args.phase
    assert not backup.exists(), 'Fresh phase directory required; preserve earlier evidence'
    assert backup.resolve().is_relative_to(external.resolve())
    backup.mkdir(parents=True)
    response = PRIVATE / f'recovery-{args.phase}-response.json'
    trace = PRIVATE / f'recovery-{args.phase}-trace.jsonl'
    assert not response.exists() and not trace.exists()
    runtime = {str(path): digest(path) for path in (ROOT / 'solidworks_mcp').rglob('*.py')}
    sources = {str(path): digest(path) for path in (Path(__file__), FIXTURE, SESSION, WATCH / 'commands.txt', ROOT/'solidworks_mcp_server.py',
                                                  LAB / 'evidence_storage.py', LAB / 'sensor_case_coordinator_v1.py')}
    report = {'phase': args.phase, 'pid': args.pid, 'start_time': args.start_time, 'passed': False,
              'started_at': datetime.now(timezone.utc).isoformat(), 'backup_directory': str(backup),
              'runtime_sha256': runtime, 'source_sha256': sources, 'cycles': [],
              'cad_launches': 0, 'direct_cad_calls': 0, 'model_edits': 0,
              'native_preferences_modified': False, 'snapshot_geometry_reopen_verified': False}
    marker = backup / 'requested.stop'
    current_worker = None
    worker_attempted = False
    with response.open('x', encoding='utf-8') as output, trace.open('x', encoding='utf-8') as events, ExitStack() as handles:
        def save():
            output.seek(0); json.dump(report, output, indent=2); output.truncate(); output.flush(); os.fsync(output.fileno())
        def event(name, **data):
            events.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(), 'event': name, **data}) + '\n')
            events.flush(); os.fsync(events.fileno())
        def held(pid, image, start):
            handle = win32api.OpenProcess(win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
            handles.callback(handle.Close)
            assert win32event.WaitForSingleObject(handle, 0) == win32con.WAIT_TIMEOUT
            assert Path(win32process.GetModuleFileNameEx(handle, 0)).resolve() == Path(image).resolve()
            assert abs(win32process.GetProcessTimes(handle)['CreationTime'].timestamp() - datetime.fromisoformat(start).timestamp()) < .001
            return handle
        save()
        try:
            state = read(SESSION)
            assert state['ready'] and (state['pid'], state['start_time']) == (args.pid, args.start_time)
            ready = read(WATCH / 'ready.json')
            assert ready['attached'] and ready['pid'] == args.pid and Path(ready['session_file']).resolve() == SESSION.resolve()
            cdb_start = coordinator.process_identity(ready['debugger_pid'], coordinator.CDB)
            cdb_command = coordinator.command_line(ready['debugger_pid'])
            assert '-G' in cdb_command and cdb_command[cdb_command.index('-p') + 1] == str(args.pid)
            assert Path(cdb_command[cdb_command.index('-cf') + 1]).resolve() == (WATCH / 'commands.txt').resolve()
            cad_handle = held(args.pid, coordinator.CAD, args.start_time)
            cdb_handle = held(ready['debugger_pid'], coordinator.CDB, cdb_start)
            report['watcher']={'pid':ready['debugger_pid'],'start_time':cdb_start,'image':str(coordinator.CDB)}
            save()
            def guard():
                assert win32event.WaitForSingleObject(cad_handle, 0) == win32con.WAIT_TIMEOUT, 'Owned CAD exited'
                assert win32event.WaitForSingleObject(cdb_handle, 0) == win32con.WAIT_TIMEOUT, 'Owned native watcher exited'
                assert all(not (WATCH / name).exists() for name in ('exception.dmp', 'breakpoint.dmp', 'result.json', 'stop.request'))
                for name in ('console.txt', 'engine.txt'):
                    path = WATCH / name
                    if path.exists():
                        assert not any(line.strip() in {'CAPTURED_OWNED_AV', 'CAPTURED_OWNED_BREAKPOINT'}
                                       for line in path.read_text(encoding='utf-8', errors='replace').splitlines()), 'Native fault marker'
                assert FaultStore().read(args.pid, lambda _: args.start_time) is None
                assert digest(PART) == baseline['sha256'], 'Original private baseline changed on disk'
                assert all(digest(path) == value for path, value in sources.items())
                assert all(digest(path) == value for path, value in runtime.items())
                current = read(SESSION)
                assert (current['pid'], current['start_time']) == (args.pid, args.start_time)
                evidence_storage.require_sandisk()
            guard()
            environment = {'SOLIDWORKS_TARGET_PID': str(args.pid), 'SOLIDWORKS_SESSION_FILE': str(SESSION),
                'SOLIDWORKS_AUTO_LAUNCH': '0', 'SOLIDWORKS_RECOVERY_MONITOR': '1',
                'SOLIDWORKS_RECOVERY_DIRECTORY': str(backup), 'SOLIDWORKS_RECOVERY_INTERVAL': '2',
                'SOLIDWORKS_RECOVERY_ALL_DOCUMENTS': '0', 'SOLIDWORKS_RECOVERY_ASSEMBLIES': '0',
                'SOLIDWORKS_RECOVERY_DRAWINGS': '0', 'SOLIDWORKS_RECOVERY_BACKGROUND_ACTIVATION': '0',
                'SOLIDWORKS_JOURNAL_WARNING_ACTION': 'manual',
                'SOLIDWORKS_MCP_LOG': str(PRIVATE / 'recovery-worker-{server_pid}.log')}
            # This disposable verification process alone gets these variables;
            # no workspace config or another process environment is rewritten.
            os.environ.update(environment); report['worker_environment'] = environment; save()
            count = 2 if args.phase == 'lifecycle' else 1
            for number in range(1, count + 1):
                guard(); event('ensure_begin', cycle=number)
                worker_attempted = True
                worker = (asyncio.run(native_auto_ensure(args.pid,args.start_time,environment,report,save,guard))
                          if args.phase=='backup' else service.ensure_recovery_worker(args.pid))
                assert worker and not worker['reused']
                current_worker = worker
                handle = held(worker['worker_pid'], sys._base_executable, worker['worker_start_time'])
                assert Path(worker['status_file']).resolve() == (backup / 'monitor.json').resolve()
                cycle = {'number': number, 'worker': worker}; report['cycles'].append(cycle); save()
                event('ensure_end', cycle=number, worker_pid=worker['worker_pid'])
                wanted = 'waiting_clean' if args.phase == 'lifecycle' else 'snapshot_complete'
                deadline = time.monotonic() + 45
                status = None
                while time.monotonic() < deadline:
                    guard(); status = read(worker['status_file'])
                    assert (status['pid'], status['process_start_time']) == (args.pid, args.start_time)
                    assert (status['worker_pid'], status['worker_start_time']) == (worker['worker_pid'], worker['worker_start_time'])
                    assert Path(status['session_file']).resolve() == SESSION.resolve()
                    assert status['status'] not in ('failed', 'stopped'), status
                    assert win32event.WaitForSingleObject(handle, 0) == win32con.WAIT_TIMEOUT, 'Worker exited early'
                    if status['status'] == wanted: break
                    time.sleep(.2)
                assert status and status['status'] == wanted, 'Worker did not reach expected native state'
                cycle['observed'] = status; save()
                if args.phase == 'backup':
                    snapshot = status['last_snapshot']; path = Path(snapshot['snapshot_path'])
                    manifest = Path(snapshot['manifest_path'])
                    assert path.resolve().is_relative_to(backup.resolve()) and manifest.resolve().is_relative_to(backup.resolve())
                    assert snapshot['status'] == 'complete' and snapshot['source_preserved'] is True
                    assert Path(snapshot['source']['path']).resolve() == PART.resolve()
                    assert snapshot['source']['dirty'] is True
                    assert snapshot['source_sha256'] == baseline['sha256']
                    assert digest(path) == snapshot['snapshot_sha256'] and path.stat().st_size == snapshot['snapshot_bytes'] > 0
                    disk_manifest = read(manifest)
                    assert disk_manifest['status'] == 'complete' and disk_manifest['snapshot_sha256'] == snapshot['snapshot_sha256']
                    cycle['snapshot_file_verified'] = {'path': str(path), 'sha256': digest(path), 'bytes': path.stat().st_size,
                                                       'manifest': str(manifest), 'geometry_reopen_required': True}
                else:
                    assert status['snapshots'] == 0, 'Lifecycle-only phase expected a clean private part'
                guard(); event('stop_requested', cycle=number)
                with marker.open('x') as stop: stop.write('Owned native verification stop\n'); stop.flush(); os.fsync(stop.fileno())
                deadline = time.monotonic() + 30
                while win32event.WaitForSingleObject(handle, 0) == win32con.WAIT_TIMEOUT and time.monotonic() < deadline:
                    guard(); time.sleep(.2)
                guard()
                assert win32event.WaitForSingleObject(handle, 0) == win32con.WAIT_OBJECT_0, 'Worker did not exit naturally'
                assert win32process.GetExitCodeProcess(handle) == 0
                stopped = read(worker['status_file'])
                assert stopped['status'] == 'stopped' and stopped['reason'] == 'stop_requested'
                assert (stopped['pid'], stopped['process_start_time']) == (args.pid, args.start_time)
                assert (stopped['worker_pid'], stopped['worker_start_time']) == (worker['worker_pid'], worker['worker_start_time'])
                cycle['stopped'] = stopped; cycle['natural_exit_code'] = 0; current_worker = None
                worker_attempted = False
                event('worker_exited', cycle=number, worker_pid=worker['worker_pid']); save()
                if number < count:
                    marker.rename(backup / f'consumed-cycle-{number}.stop')
            if count == 2:
                first, second = report['cycles']
                assert first['worker']['worker_start_time'] != second['worker']['worker_start_time']
                assert first['observed']['startup_token'] != second['observed']['startup_token']
                assert list((backup / 'retired-startups').glob('*-monitor.json'))
            guard(); report.update(passed=True, completed_at=datetime.now(timezone.utc).isoformat()); save()
        except BaseException as error:
            report['error'] = {'type': type(error).__name__, 'message': str(error)}
            if current_worker is not None or worker_attempted:
                # File-only cancellation is safe even after a native fault. No
                # additional COM, document cleanup, or process kill is attempted.
                try:
                    marker.touch(exist_ok=True); report['failure_stop_requested'] = True
                except Exception as stop_error:
                    report['failure_stop_error'] = str(stop_error)
            report['failed_at'] = datetime.now(timezone.utc).isoformat(); save()
    print(json.dumps({'passed': report['passed'], 'response': str(response), 'error': report.get('error')}, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
