"""Run package repair against an explicitly configured owned helper session."""
import json,os,sys,uuid,time
from pathlib import Path
from .automation.managed_session import process_identity,write_state
from .package_repair import validate_private_package,validate_repair_result
from .desktop_process import start_desktop_process

def configured_processor(environment=None):
    environment=dict(os.environ if environment is None else environment)
    helper=environment.get('SOLIDWORKS_RECOVERY_REPAIR_SESSION_FILE')
    if helper is None:return None
    helper=Path(helper);source=Path(environment.get('SOLIDWORKS_SESSION_FILE',''))
    if not helper.is_absolute() or not source.is_absolute() or helper.resolve()==source.resolve():
        raise ValueError('Repair helper and source require separate absolute owned session files')
    def process(evidence):
        root,_,_=validate_private_package(evidence)
        owner=json.loads(helper.read_text(encoding='utf-8'))
        if (owner.get('role')!='recovery_repair'
                or owner.get('source_session_file')!=str(source.resolve())
                or int(owner['pid'])==int(evidence['pid'])
                or process_identity(int(owner['pid']))!=owner['start_time']):
            raise RuntimeError('Configured repair helper is absent or not owned by this source session; no CAD was launched')
        token=uuid.uuid4().hex
        request=root/('repair-request-'+token+'.json');response=root/('repair-result-'+token+'.json')
        write_state(request,{'token':token,'source_session_file':str(source.resolve()),'evidence':evidence})
        # A child of the MCP stdio job stalled before Python initialization in
        # the real dual-PID test. Use the same desktop-parent creation path as
        # persistent recovery workers; inherit no MCP pipes or job membership.
        start_desktop_process(sys.executable,Path(__file__).resolve().parents[1],
            ['-m','solidworks_mcp.package_repair_worker','--session-file',str(helper),
             '--request',str(request),'--response',str(response),'--configure-helper-environment'])
        deadline=time.monotonic()+900
        while not response.exists() and time.monotonic()<deadline:time.sleep(0.5)
        if not response.exists():raise RuntimeError('Repair worker response timed out; no replacement worker was launched')
        result=json.loads(response.read_text(encoding='utf-8'))
        if result.get('token')!=token:raise RuntimeError('Repair worker response token mismatch')
        if result.get('status')!='repaired':
            raise RuntimeError(result.get('error','Independent package repair failed'))
        validate_repair_result(evidence,result)
        return result
    return process
