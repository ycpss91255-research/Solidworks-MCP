"""Root-run synthetic legacy retirement; OS/files only, no CAD/backend/launch.

Requires the successful owned native lifecycle proof. Its naturally exited first
worker supplies the synthetic old PID; the actual session/reservations stay intact.
"""
from datetime import datetime
from pathlib import Path
import argparse
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(1,str(ROOT/'tests'))
import verify_owned_recovery_native as own


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid',type=int,required=True)
    parser.add_argument('--start-time',required=True)
    args=parser.parse_args()
    if sys.flags.optimize: raise RuntimeError('Python -O is forbidden')
    assert ROOT==Path('C:/Users/yunchien.chen/mcp/solidworks-mcp-recovery-reservation-test')
    assert Path.cwd().resolve()==ROOT and Path(os.environ['PYTHONPATH']).resolve()==ROOT
    sys.path.insert(2,str(own.LAB))
    import evidence_storage
    import sensor_case_coordinator_v1 as coordinator
    import win32api,win32con,win32event,win32process
    from solidworks_mcp import recovery_service as service
    from solidworks_mcp.automation.managed_session import process_identity

    prior=own.read(own.PRIVATE/'recovery-lifecycle-response.json')
    assert prior['passed'] and (prior['pid'],prior['start_time'])==(args.pid,args.start_time)
    first=prior['cycles'][0]
    assert first['natural_exit_code']==0 and first['stopped']['reason']=='stop_requested'
    old=first['worker'];assert service.worker_identity(old['worker_pid']) is None
    actual=own.read(own.SESSION)
    assert (actual['pid'],actual['start_time'])==(args.pid,args.start_time)
    assert process_identity(args.pid)==args.start_time
    session=own.PRIVATE/'recovery-synthetic-legacy-session.json'
    response=own.PRIVATE/'recovery-synthetic-legacy-response.json'
    directory=evidence_storage.require_sandisk()/'recovery-reservation-native-part-v1'/'synthetic-legacy'
    assert not session.exists() and not response.exists() and not directory.exists()
    runtime={str(p):own.digest(p) for p in (ROOT/'solidworks_mcp').rglob('*.py')}
    original_sha=own.digest(own.SESSION)
    handle=win32api.OpenProcess(win32con.SYNCHRONIZE|win32con.PROCESS_QUERY_INFORMATION|win32con.PROCESS_VM_READ,False,args.pid)
    try:
        assert Path(win32process.GetModuleFileNameEx(handle,0)).resolve()==coordinator.CAD.resolve()
        assert abs(win32process.GetProcessTimes(handle)['CreationTime'].timestamp()-datetime.fromisoformat(args.start_time).timestamp())<.001
        directory.mkdir(parents=True)
        with session.open('x',encoding='utf8') as stream:json.dump(actual,stream)
        pending=directory/'worker-startup.json'
        record={'kind':'recovery_worker_startup','pid':old['worker_pid'],
                'process_start_time':old['worker_start_time'],'session_file':str(session.resolve()),
                'startup_token':'synthetic-owned-lifecycle-exited-worker','synthetic_fixture':True}
        with pending.open('x',encoding='utf8') as stream:json.dump(record,stream)
        raw=pending.read_bytes()
        result={'passed':False,'synthetic':True,'actual_other_session_metadata_changed':False,
                'pid':args.pid,'start_time':args.start_time,'session_file':str(session),
                'directory':str(directory),'runtime_sha256':runtime,
                'source_sha256':own.digest(__file__),'cad_calls':0,'worker_or_cad_launches':0}
        try:
            assert win32event.WaitForSingleObject(handle,0)==win32con.WAIT_TIMEOUT
            assert service.worker_identity(old['worker_pid']) is None
            retired=service.retire_stale_startup(session,directory)
            archive=Path(retired['reservation_archive'])
            assert retired['retired'] and not retired['worker_launched']
            assert archive.resolve().is_relative_to(directory.resolve()) and archive.read_bytes()==raw
            assert not pending.exists() and not (directory/'monitor.json').exists()
            assert win32event.WaitForSingleObject(handle,0)==win32con.WAIT_TIMEOUT
            assert own.digest(own.SESSION)==original_sha and process_identity(args.pid)==args.start_time
            assert all(own.digest(path)==value for path,value in runtime.items())
            result.update(passed=True,retirement=retired,archive_sha256=own.digest(archive),original_bytes_preserved=True)
        except BaseException as error:
            result['error']={'type':type(error).__name__,'message':str(error)}
        with response.open('x',encoding='utf8') as stream:
            json.dump(result,stream,indent=2);stream.flush();os.fsync(stream.fileno())
        print(json.dumps({'passed':result['passed'],'response':str(response),'error':result.get('error')},indent=2))
        return 0 if result['passed'] else 1
    finally:handle.Close()


if __name__=='__main__':raise SystemExit(main())
