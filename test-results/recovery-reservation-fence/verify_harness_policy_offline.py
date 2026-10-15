"""Exercise the actual embedded MCP policy script using fake CAD/launcher only."""
import asyncio
from contextlib import asynccontextmanager, redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('native_harness',ROOT/'tests/verify_owned_recovery_native.py')
harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)
from solidworks_mcp import recovery_service, recovery_policy, native_fault
from solidworks_mcp.automation import managed_session
import win32api, win32event, win32process

def exercise(enabled, inject_fault=False, watcher_exit=False):
    with tempfile.TemporaryDirectory(prefix='policy-fake-',dir=Path(__file__).parent) as folder:
        private=Path(folder); calls=[]; launches=[]; params_seen=[]
        watcher={'pid':456,'start_time':'2026-10-15T00:00:00+00:00','image':str(private/'fake-cdb.exe')}
        report={'watcher':watcher}
        class Handle:
            closed=False
            def Close(self): self.closed=True
        handle=Handle()
        class App:
            GetProcessID=123
            def GetUserPreferenceToggle(self,n):
                calls.append(n)
                if inject_fault: (private/'exception.dmp').touch()
                return enabled
            def GetUserPreferenceIntegerValue(self,n):
                calls.append(n);return 5 if n==3 else 2
        def ensure(pid,app=None):
            launches.append(os.environ['SOLIDWORKS_RECOVERY_MONITOR'])
            if os.environ['SOLIDWORKS_RECOVERY_MONITOR']=='auto':
                policy=recovery_policy.automatic_policy(app,pid,os.environ)
                if not policy['enabled']: return None
                assert policy['settings']['interval_seconds']==300
            return {'worker_pid':999,'worker_start_time':'fake-only'}
        class Reply:
            def __init__(self,text): self.text=text
            def model_dump(self,**kwargs): return {'content':[{'type':'text','text':self.text}],'isError':False}
        class Client:
            def __init__(self,*args,**kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self,*args): pass
            async def initialize(self): pass
            async def call_tool(self,name,arguments):
                if name=='connect_solidworks': return Reply('[SUCCESS] fake connect')
                stream=io.StringIO()
                with redirect_stdout(stream): exec(compile(arguments['code'],'fake-policy-request','exec'),{'sw':App()})
                return Reply('[SUCCESS] === Output ===\n'+stream.getvalue())
        @asynccontextmanager
        async def stdio(params):
            params_seen.append(params)
            assert params.env['SOLIDWORKS_RECOVERY_MONITOR']=='0'
            assert 'SOLIDWORKS_RECOVERY_INTERVAL' not in params.env
            yield None,None
        environment={'SOLIDWORKS_SESSION_FILE':str(private/'session.json'),
                     'SOLIDWORKS_RECOVERY_DIRECTORY':str(private/'backup'),
                     'SOLIDWORKS_RECOVERY_ALL_DOCUMENTS':'0','SOLIDWORKS_RECOVERY_BACKGROUND_ACTIVATION':'0'}
        with patch.dict(os.environ,dict(environment,LOCALAPPDATA=str(private),USERPROFILE=str(private)),clear=True), \
             patch.object(harness,'PRIVATE',private), patch.object(harness,'WATCH',private), \
             patch('mcp.ClientSession',Client), patch('mcp.client.stdio.stdio_client',stdio), \
             patch.object(recovery_service,'ensure_recovery_worker',side_effect=ensure), \
             patch.object(managed_session,'process_identity',return_value='fake-start'), \
             patch.object(native_fault.FaultStore,'read',return_value=None), \
             patch.object(win32api,'OpenProcess',return_value=handle), \
             patch.object(win32process,'GetModuleFileNameEx',return_value=watcher['image']), \
             patch.object(win32process,'GetProcessTimes',return_value={'CreationTime':datetime.fromisoformat(watcher['start_time'])}), \
             patch.object(win32event,'WaitForSingleObject',side_effect=lambda *_:0 if watcher_exit and calls else 258):
            if inject_fault or watcher_exit:
                try: asyncio.run(harness.native_auto_ensure(123,'fake-start',environment,report,lambda:None,lambda:None))
                except AssertionError: pass
                else: raise AssertionError('native marker failed to stop preference reads')
                assert calls==[319] and launches==[]
            else:
                worker=asyncio.run(harness.native_auto_ensure(123,'fake-start',environment,report,lambda:None,lambda:None))
                assert worker['worker_pid']==999
                assert report['native_auto_policy']['auto_worker_started'] is enabled
                assert launches==(['auto'] if enabled else ['auto','1'])
            assert handle.closed,'held watcher handle leaked'
            rows=[json.loads(line) for line in (private/'recovery-auto-policy-trace.jsonl').read_text().splitlines()]
            assert rows and params_seen
            return {'enabled':enabled,'injected_fault':inject_fault,'watcher_exit':watcher_exit,'passed':True,
                    'preference_calls':calls,'fake_ensure_modes':launches,'trace_rows':len(rows)}

results=[exercise(True),exercise(False),exercise(True,True),exercise(True,watcher_exit=True)]
path=Path(__file__).with_suffix('.json')
path.write_text(json.dumps({'passed':True,'actual_cad_calls':0,'actual_worker_launches':0,
    'harness_sha256':hashlib.sha256(Path(harness.__file__).read_bytes()).hexdigest(),
    'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':results},indent=2))
print(path.read_text())
