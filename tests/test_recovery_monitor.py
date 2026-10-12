import json,tempfile,unittest,sys,io
from types import SimpleNamespace
from contextlib import nullcontext,redirect_stdout
from pathlib import Path
from unittest.mock import Mock,patch
from solidworks_mcp.recovery_monitor import run_monitor,validate_status_path,CadBackend,main

class Clock:
    def __init__(self):self.time=0
    def now(self):return self.time
    def sleep(self,duration):self.time+=duration

class Backend:
    def __init__(self,clock,states=None):
        self.clock=clock;self.states=iter(states or ['dirty']*10)
        self.calls=[];self.connects=0;self.closed=0;self.failure=None
    def connect(self):
        self.connects+=1
        return {'success':True}
    def probe(self):return {'state':next(self.states)}
    def snapshot(self):
        self.calls.append(self.clock.now())
        self.clock.time+=2
        if self.failure:return {'success':False,'message':self.failure}
        return {'success':True,'data':{'status':'complete','pid':123,'process_start_time':'start','generation':len(self.calls)}}
    def close(self):self.closed+=1

class MonitorTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.status=self.root/'monitor.json'
        self.clock=Clock();self.backend=Backend(self.clock)
    def run_monitor(self,**kwargs):
        options={'max_ticks':3,'identity_reader':lambda pid:'start','dialog_reader':lambda pid:False,
                 'clock':self.clock.now,'sleep':self.clock.sleep}
        options.update(kwargs)
        return run_monitor(123,'start',self.root,self.status,1,self.backend,**options)
    def test_saves_sequentially_after_previous_save_completes(self):
        result=self.run_monitor()
        self.assertEqual(self.backend.calls,[0,3,6])
        self.assertEqual(result['snapshots'],3)
        self.assertEqual(result['reason'],'tick_limit')
        self.assertEqual(self.backend.connects,1);self.assertEqual(self.backend.closed,1)
        self.assertEqual(json.loads(self.status.read_text())['pid'],123)
    def test_clean_unsupported_and_missing_documents_do_not_save(self):
        self.backend.states=iter(['clean','unsupported_document','no_document'])
        result=self.run_monitor()
        self.assertEqual(result['snapshots'],0);self.assertEqual(self.backend.calls,[])
    def test_visible_dialogs_do_not_connect_or_get_dismissed(self):
        result=self.run_monitor(dialog_reader=lambda pid:True)
        self.assertEqual(result['snapshots'],0);self.assertEqual(self.backend.connects,0)
        self.assertEqual(self.backend.calls,[])
    def test_pid_identity_change_stops_without_retarget_or_reconnect(self):
        identities=iter(['start','changed'])
        result=self.run_monitor(identity_reader=lambda pid:next(identities))
        self.assertEqual(result['reason'],'target_exited_or_identity_changed')
        self.assertEqual(result['snapshots'],1);self.assertEqual(self.backend.connects,1)
    def test_snapshot_error_is_terminal(self):
        self.backend.failure='copy failed'
        result=self.run_monitor()
        self.assertEqual(result['status'],'failed');self.assertEqual(self.backend.connects,1)
        self.assertEqual(len(self.backend.calls),1);self.assertEqual(result['snapshots'],0)
    def test_incomplete_or_foreign_snapshot_cannot_be_counted(self):
        for report in ({'status':'writing','pid':123,'process_start_time':'start'},
                       {'status':'complete','pid':456,'process_start_time':'start'}):
            with self.subTest(report=report):
                self.backend.snapshot=Mock(return_value={'success':True,'data':report})
                result=self.run_monitor()
                self.assertEqual(result['status'],'failed');self.assertEqual(result['snapshots'],0)
    def test_connection_error_is_not_retried(self):
        self.backend.connect=Mock(return_value={'success':False,'message':'COM bind failed'})
        result=self.run_monitor()
        self.assertEqual(result['status'],'failed');self.backend.connect.assert_called_once()
        self.assertEqual(self.backend.calls,[])
    def test_stop_request_leaves_cad_untouched(self):
        result=self.run_monitor(stop=lambda:True)
        self.assertEqual(result['reason'],'stop_requested')
        self.assertEqual(self.backend.connects,0);self.assertEqual(self.backend.calls,[])
    def test_unrelated_json_cannot_be_overwritten(self):
        self.status.write_text('{"kind":"user-config"}')
        with self.assertRaisesRegex(ValueError,'unrelated'):self.run_monitor()
        self.assertEqual(self.status.read_text(),'{"kind":"user-config"}')
    def test_another_sessions_status_is_preserved(self):
        self.status.write_text(json.dumps({'kind':'part_recovery_monitor','session_file':str(self.root/'other.json')}))
        before=self.status.read_text()
        with self.assertRaisesRegex(ValueError,'another session'):
            self.run_monitor(session_file=self.root/'own.json')
        self.assertEqual(self.status.read_text(),before)
    def test_status_cannot_overwrite_cad_file_or_leave_private_directory(self):
        for destination in (self.root/'part.SLDPRT',self.root.parent/'foreign.json'):
            with self.subTest(destination=destination),self.assertRaisesRegex(ValueError,'inside'):
                validate_status_path(self.root,destination)
    def test_backend_disables_inherited_managed_startup(self):
        automation=Mock();automation._auto_launch=True
        with patch('solidworks_mcp.automation.SolidWorksAutomation',return_value=automation):
            backend=CadBackend(123,self.root)
        self.assertFalse(automation._auto_launch)
        self.assertEqual(automation._target_pid,'123')
        self.assertEqual(automation._configured_target,'123')
        automation.connect.assert_not_called()
    def test_assembly_child_edits_trigger_copy_only_when_explicitly_enabled(self):
        parent_object=object();child_object=object()
        parent=SimpleNamespace(_oleobj_=parent_object,GetType=2,GetSaveFlag=False)
        child=SimpleNamespace(_oleobj_=child_object,GetType=1,GetSaveFlag=True)
        component=SimpleNamespace(_oleobj_=object(),GetModelDoc2=child)
        raw=SimpleNamespace(_oleobj_=object(),RevisionNumber='31.5')
        app=SimpleNamespace(GetProcessID=123,CommandInProgress=False,ActiveDoc=parent)
        assembly=SimpleNamespace(GetComponents=lambda recursive:[component])
        module=SimpleNamespace(ISldWorks=lambda obj:app,IAssemblyDoc=lambda obj:assembly,
                               IComponent2=lambda obj:component,
                               IModelDoc2=lambda obj:parent if obj is parent_object else child)
        automation=Mock();automation.is_connected=True;automation.app=raw
        with patch('solidworks_mcp.automation.SolidWorksAutomation',return_value=automation), \
             patch('win32com.client.gencache.EnsureModule',return_value=module), \
             patch.dict('os.environ',{'SOLIDWORKS_RECOVERY_ASSEMBLIES':'0'}):
            backend=CadBackend(123,self.root)
            self.assertEqual(backend.probe()['state'],'unsupported_document')
            backend.assembly_enabled=True
            self.assertEqual(backend.probe()['state'],'dirty')
            child.GetSaveFlag=False
            self.assertEqual(backend.probe()['state'],'clean')
    def test_cli_existing_stop_marker_does_not_connect(self):
        session=self.root/'session.json';marker=self.root/'requested.stop'
        session.write_text(json.dumps({'pid':123,'start_time':'start'}));marker.touch()
        args=['monitor','--session-file',str(session),'--directory',str(self.root),
              '--status-file',str(self.status),'--interval','1','--stop-file',str(marker)]
        with patch.object(sys,'argv',args),patch('solidworks_mcp.recovery_monitor.process_identity',return_value='start'), \
             patch('solidworks_mcp.recovery_monitor.monitor_lock',return_value=nullcontext()), \
             patch('solidworks_mcp.recovery_monitor.CadBackend',return_value=self.backend),redirect_stdout(io.StringIO()):
            main()
        self.assertEqual(self.backend.connects,0)
        self.assertEqual(json.loads(self.status.read_text())['reason'],'stop_requested')
