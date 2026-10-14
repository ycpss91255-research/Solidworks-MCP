"""Opt-in private-fixture acceptance through a fresh PID-bound MCP connection.

No launch, generic COM activation, automatic repair or fallback. Use a manifest
with fixture_dir, session_file, pid, expected (both configurations), source_hashes
and protected_pids. --roundtrip explicitly saves only the private fixture.
"""
import argparse
import asyncio
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(manifest, roundtrip=False):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from solidworks_mcp.automation.managed_session import process_identity
    fixture = Path(manifest['fixture_dir'])
    session_file = Path(manifest['session_file'])
    assert fixture.is_absolute() and session_file.is_absolute(), 'absolute private paths required'
    fixture, session_file = fixture.resolve(), session_file.resolve()
    state = json.loads(session_file.read_text(encoding='utf-8'))
    pid = manifest['pid']
    assert type(pid) is int and pid > 0 and state['pid'] == pid and state['ready']
    identity = process_identity(pid)
    assert identity == state['start_time'], 'owned session identity mismatch; never reconnect to a different PID'
    protected = {p:process_identity(p) for p in manifest.get('protected_pids', [])}
    assert pid not in protected, 'test PID must not be a protected working PID'
    expected = manifest['expected']
    assert set(expected) == {'橫撐','斜撐'}, 'both configurations required'
    assert all(not Path(p).resolve().is_relative_to(fixture) for p in manifest['source_hashes']), 'original sources must be outside the private fixture'
    report = dict(pid=pid, identity=identity, start=datetime.now().astimezone().isoformat(),
                  roundtrip=roundtrip, steps=[], passed=False, expected=expected,
                  source_hashes=manifest['source_hashes'],
                  runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  acceptance_sha256=hashlib.sha256((ROOT/'solidworks_mcp/diagnostics/configuration_acceptance.py').read_bytes()).hexdigest())
    output = fixture/'configuration-regression-result.json'
    def save():output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def sources_intact():
        try:
            return all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
                       for p,h in manifest['source_hashes'].items())
        except OSError:
            return False
    assert manifest['source_hashes'] and sources_intact(), 'source baseline mismatch'
    env = dict(os.environ, SOLIDWORKS_TARGET_PID=str(pid),SOLIDWORKS_AUTO_LAUNCH='0',
        SOLIDWORKS_SESSION_FILE=str(session_file),SOLIDWORKS_RECOVERY_MONITOR='0',
        SOLIDWORKS_JOURNAL_WARNING_ACTION='dismiss',
        SOLIDWORKS_MCP_LOG=str(fixture/f'configuration-regression-{pid}.log'))
    try:
        async with stdio_client(StdioServerParameters(command=sys.executable,
                args=[str(ROOT/'solidworks_mcp_server.py')],env=env)) as (reader,writer):
            async with ClientSession(reader,writer,read_timeout_seconds=timedelta(seconds=120)) as client:
                await client.initialize()
                async def call(label,tool,args):
                    row={'label':label,'start':datetime.now().astimezone().isoformat(),'arguments':args};report['steps'].append(row);save()
                    response=(await client.call_tool(tool,args)).content[0].text
                    row.update(response=response,end=datetime.now().astimezone().isoformat())
                    if not response.startswith('[SUCCESS]') and '\nDetails: ' in response:
                        details=json.loads(response.split('\nDetails: ',1)[1])
                        if details.get('operation_cancelled'):
                            report['deferred_reason']='memory_warning_cancelled'
                    save()
                    print(label,response[:160],flush=True)
                    assert response.startswith('[SUCCESS]'), response
                prefix=(f"from pathlib import Path\nfrom win32com.client import gencache\n"
                    "m=gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,31,0)\n"
                    f"sw=m.ISldWorks(sw._oleobj_)\nassert sw.GetProcessID()=={pid}\nprivate=Path({str(fixture)!r})\n"
                    "assert all(Path(m.IModelDoc2(x._oleobj_).GetPathName()).is_relative_to(private) for x in sw.GetDocuments() or [])\n")
                async def code(label,source):await call(label,'execute_python',{'code':prefix+source})
                await call('connect','connect_solidworks',{})
                await code('private_scope_preflight',"result={'scope_verified':True}")
                await call('open_private_fixture','open_document',{'filepath':str(fixture/'支架.SLDASM'),'memory_warning_action':'cancel'})
                async def verify(phase):
                    for name,spec in expected.items():
                        observation_file=fixture/f'configuration-{phase}-{name}.json'
                        await code(f'{phase}_{name}',
                            "import json\nfrom solidworks_mcp.diagnostics.configuration_acceptance import observe_configuration,assert_geometry\n"
                            "d=m.IModelDoc2(sw.GetOpenDocumentByName(str(private/'支撐條.SLDPRT'))._oleobj_)\n"
                            "assert sw.ActivateDoc3(d.GetTitle(),False,0,0)[0]\n"
                            f"d.ShowConfiguration2({name!r})\nrebuild=bool(d.ForceRebuild3(False))\n"
                            f"observation=observe_configuration(sw,str(private/'支撐條.SLDPRT'),str(private),{pid},rebuild)\n"
                            f"Path({str(observation_file)!r}).write_text(json.dumps(observation,ensure_ascii=False,indent=2),encoding='utf-8')\n"
                            f"assert_geometry(observation,{spec!r})\nresult=observation")
                await verify('before_save')
                if roundtrip:
                    await code('save_private_fixture',"rows=[]\nfor name in ['支撐條.SLDPRT','支柱.SLDPRT','支架.SLDASM']:\n d=m.IModelDoc2(sw.GetOpenDocumentByName(str(private/name))._oleobj_)\n ret=d.Save3(1,0,0)\n rows.append([name,list(ret)])\n assert ret[0] and ret[1]==0 and ret[2]==0,(name,ret)\nresult=rows")
                    await code('close_before_reopen',"sw.CloseAllDocuments(True)\nassert not sw.GetFirstDocument()\nresult={'closed':True}")
                    await call('reopen_private_fixture','open_document',{'filepath':str(fixture/'支架.SLDASM'),'memory_warning_action':'cancel'})
                    await verify('after_reopen')
                    await code('close_after_reopen',"sw.CloseAllDocuments(True)\nassert not sw.GetFirstDocument()\nresult={'closed':True}")
                report['passed']=True
    except Exception as exc:
        report['error']=repr(exc)
        raise
    finally:
        report['source_hashes_preserved']=sources_intact()
        report['protected_identities_preserved']=all(process_identity(p)==identity for p,identity in protected.items())
        report['target_identity_preserved']=process_identity(pid)==identity
        report['passed']=report['passed'] and all(report[k] for k in
            ('source_hashes_preserved','protected_identities_preserved','target_identity_preserved'))
        save()
    assert report['passed'],report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--roundtrip',action='store_true')
    args=parser.parse_args()
    asyncio.run(run(json.loads(args.manifest.read_text(encoding='utf-8')),args.roundtrip))
