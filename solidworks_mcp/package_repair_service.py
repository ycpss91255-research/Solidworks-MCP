"""Run package repair against an explicitly configured owned helper session."""
import json,os,subprocess,sys,uuid
from pathlib import Path
from .automation.managed_session import process_identity,write_state
from .package_repair import validate_private_package,validate_repair_result

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
        env={k:v for k,v in environment.items() if not k.startswith('SOLIDWORKS_')}
        env.update(SOLIDWORKS_TARGET_PID=str(owner['pid']),SOLIDWORKS_SESSION_FILE=str(helper),
                   SOLIDWORKS_AUTO_LAUNCH='0',SOLIDWORKS_RECOVERY_MONITOR='0')
        completed=subprocess.run([sys.executable,'-m','solidworks_mcp.package_repair_worker',
            '--session-file',str(helper),'--request',str(request),'--response',str(response)],
            cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,
            timeout=900,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if not response.exists():raise RuntimeError('Repair worker produced no correlated response')
        result=json.loads(response.read_text(encoding='utf-8'))
        if result.get('token')!=token:raise RuntimeError('Repair worker response token mismatch')
        if completed.returncode or result.get('status')!='repaired':
            raise RuntimeError(result.get('error','Independent package repair failed'))
        validate_repair_result(evidence,result)
        return result
    return process
