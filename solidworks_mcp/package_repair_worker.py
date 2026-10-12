"""One repair request using only the explicitly configured helper PID."""
import argparse,json,os
from pathlib import Path
from .automation.managed_session import process_identity,write_state
from .package_repair import repair_private_assembly,validate_private_package
from .recovery_snapshot import get0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('session-file','request','response'):parser.add_argument('--'+flag,type=Path,required=True)
    args=parser.parse_args()
    if not all(p.is_absolute() for p in (args.session_file,args.request,args.response)):
        parser.error('Repair worker paths must be absolute')
    owner=json.loads(args.session_file.read_text(encoding='utf-8'))
    request=json.loads(args.request.read_text(encoding='utf-8'));evidence=request['evidence']
    root,_,_=validate_private_package(evidence)
    if (not args.request.resolve().is_relative_to(root) or not args.response.resolve().is_relative_to(root)
            or args.request.resolve()==args.response.resolve()):parser.error('Request and response must be separate private generation files')
    if owner.get('source_session_file')!=request['source_session_file']:
        parser.error('Repair helper belongs to another source session')
    pid=int(owner['pid']);source_pid=int(evidence['pid']);identity=evidence['process_start_time']
    source_session=Path(request['source_session_file'])
    source_owner=json.loads(source_session.read_text(encoding='utf-8'))
    if int(source_owner['pid'])!=source_pid or source_owner['start_time']!=identity:
        parser.error('Request source identity does not match its owned session')
    if (os.environ.get('SOLIDWORKS_TARGET_PID')!=str(pid)
            or Path(os.environ.get('SOLIDWORKS_SESSION_FILE','')).resolve()!=args.session_file.resolve()
            or os.environ.get('SOLIDWORKS_AUTO_LAUNCH')!='0'):
        parser.error('Repair worker is not configured to its exact helper PID')
    result={'token':request['token'],'status':'failed'};automation=None
    try:
        def verify_source():
            if process_identity(source_pid)!=identity:raise RuntimeError('Source CAD exited or changed during independent repair')
            current_source=json.loads(source_session.read_text(encoding='utf-8'))
            current_helper=json.loads(args.session_file.read_text(encoding='utf-8'))
            if (int(current_source['pid'])!=source_pid or current_source['start_time']!=identity
                    or int(current_helper['pid'])!=pid or current_helper['start_time']!=owner['start_time']
                    or current_helper.get('role')!='recovery_repair'
                    or current_helper.get('source_session_file')!=request['source_session_file']):
                raise RuntimeError('Source or helper session changed ownership during repair')
        verify_source()
        from .automation import SolidWorksAutomation
        from win32com.client import gencache
        automation=SolidWorksAutomation();automation._auto_launch=False;automation._recovery_startup_enabled=False
        reply=automation.connect()
        if not reply['success']:raise RuntimeError(reply.get('message','Configured helper connection failed'))
        major=int(str(get0(automation.app,'RevisionNumber')).split('.')[0])
        module=gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,major,0)
        app=module.ISldWorks(automation.app._oleobj_)
        from .recovery_monitor import monitor_lock
        with monitor_lock(str(args.session_file)+'.repair'):
            result.update(repair_private_assembly(app,pid,args.session_file,evidence,module,
                                                  memory_warning_action='cancel',verify_source=verify_source))
    except Exception as exc:result.update(status='failed',error=str(exc))
    finally:
        if automation is not None:automation.disconnect()
        write_state(args.response,result)
    if result['status']!='repaired':raise SystemExit(1)

if __name__=='__main__':main()
