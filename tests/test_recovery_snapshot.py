import asyncio,json,tempfile,unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock,patch
from solidworks_mcp.recovery_snapshot import snapshot_part,SnapshotError
from solidworks_mcp.automation.documents import DocumentOperations

class Part:
    def __init__(self,source):
        self.GetPathName=str(source);self.GetTitle='part';self.GetSaveFlag=True
        self.GetType=1;self.calls=[];self.save_status=0;self.change_source=False
    def SaveAs3(self,path,version,options):
        self.calls.append((path,version,options))
        if self.save_status:return self.save_status
        Path(path).write_bytes(b'unsaved six-mm geometry')
        if self.change_source:self.GetSaveFlag=False
        return 0

class App:
    GetProcessID=123
    def __init__(self,part):self.ActiveDoc=part

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.source=self.root/'source.SLDPRT';self.source.write_bytes(b'saved five-mm geometry')
        self.part=Part(self.source);self.app=App(self.part)
        self.destination=self.root/'recovery'
        for name,kwargs in (
            ('held_process',{'side_effect':lambda pid:nullcontext('start-time')}),
            ('process_identity',{'return_value':'start-time'})):
            patcher=patch('solidworks_mcp.recovery_snapshot.'+name,**kwargs)
            patcher.start();self.addCleanup(patcher.stop)
    def snapshot(self):return snapshot_part(self.app,123,self.destination)
    def test_copy_preserves_source_and_retains_unique_generations(self):
        first=self.snapshot();second=self.snapshot()
        self.assertEqual(first['status'],'complete')
        self.assertNotEqual(first['snapshot_path'],second['snapshot_path'])
        self.assertEqual(Path(first['snapshot_path']).read_bytes(),b'unsaved six-mm geometry')
        self.assertEqual(self.source.read_bytes(),b'saved five-mm geometry')
        self.assertTrue(self.part.GetSaveFlag)
        self.assertEqual(self.part.GetPathName,str(self.source))
        self.assertTrue(all(call[1:]==(0,3) for call in self.part.calls))
        self.assertEqual(json.loads(Path(first['manifest_path']).read_text())['status'],'complete')
    def test_wrong_pid_never_creates_files_or_saves(self):
        self.app.GetProcessID=456
        with self.assertRaisesRegex(ValueError,'configured PID'):self.snapshot()
        self.assertFalse(self.destination.exists());self.assertEqual(self.part.calls,[])
    def test_background_part_copy_leaves_active_document_unchanged(self):
        background_path=self.root/'background.SLDPRT';background_path.write_bytes(b'baseline')
        background=Part(background_path)
        result=snapshot_part(self.app,123,self.destination,document=background)
        self.assertEqual(result['source']['path'],str(background_path))
        self.assertEqual(result['active_before'],result['active_after'])
        self.assertIs(self.app.ActiveDoc,self.part)
        self.assertEqual(self.part.calls,[]);self.assertTrue(background.GetSaveFlag)
    def test_background_copy_that_changes_active_document_is_reported_failed(self):
        background=Part(self.source)
        save=background.SaveAs3
        def changing_save(*args):
            result=save(*args);self.app.ActiveDoc=background;self.app.ActiveDoc.GetTitle='other'
            return result
        background.SaveAs3=changing_save
        with self.assertRaisesRegex(SnapshotError,'Active document changed'):
            snapshot_part(self.app,123,self.destination,document=background)
    def test_loaded_part_can_be_copied_when_original_file_is_missing(self):
        self.source.unlink()
        result=self.snapshot()
        self.assertEqual(result['status'],'complete')
        self.assertIsNone(result['source_sha256'])
        self.assertFalse(self.source.exists())
        self.assertEqual(Path(result['snapshot_path']).read_bytes(),b'unsaved six-mm geometry')
    def test_assembly_is_rejected_without_saving_references(self):
        self.part.GetType=2
        with self.assertRaisesRegex(ValueError,'parts only'):self.snapshot()
        self.assertFalse(self.destination.exists());self.assertEqual(self.part.calls,[])
    def test_missing_document_never_creates_backup(self):
        self.app.ActiveDoc=None
        with self.assertRaisesRegex(ValueError,'No active document'):self.snapshot()
        self.assertFalse(self.destination.exists())
    def test_relative_destination_rejected_before_save(self):
        with self.assertRaisesRegex(ValueError,'absolute'):
            snapshot_part(self.app,123,'relative')
        self.assertEqual(self.part.calls,[])
    def test_save_failure_keeps_failed_evidence_and_never_falls_back(self):
        self.part.save_status=4
        with self.assertRaises(SnapshotError) as caught:self.snapshot()
        report=json.loads(Path(caught.exception.data['manifest_path']).read_text())
        self.assertEqual(report['status'],'failed');self.assertEqual(len(self.part.calls),1)
        self.assertEqual(self.source.read_bytes(),b'saved five-mm geometry')
    def test_state_change_cannot_be_reported_as_success(self):
        self.part.change_source=True
        with self.assertRaisesRegex(SnapshotError,'state or saved file changed') as caught:self.snapshot()
        self.assertEqual(caught.exception.data['status'],'failed')
    def test_pid_reuse_before_save_is_rejected(self):
        with patch('solidworks_mcp.recovery_snapshot.process_identity',return_value='different-start'):
            with self.assertRaisesRegex(SnapshotError,'identity changed'):self.snapshot()
        self.assertEqual(self.part.calls,[])

class SnapshotConnectionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.source=self.root/'source.SLDPRT'
        self.source.write_bytes(b'saved baseline')
        self.part=Part(self.source);self.destination=self.root/'recovery'
    def test_disconnected_snapshot_does_not_trigger_managed_startup(self):
        automation=Mock(spec=DocumentOperations)
        automation.is_connected=False
        automation._target_pid='123'
        automation.connect=Mock(side_effect=AssertionError('Must not launch or reconnect'))
        automation._result=lambda success,message,error_code=None,data=None:{'success':success,'message':message,'data':data}
        result=DocumentOperations.create_recovery_snapshot(automation,'C:/private/recovery')
        self.assertFalse(result['success']);automation.connect.assert_not_called()
        self.assertEqual(result['data']['configured_pid'],'123')
    def test_mcp_schema_and_dispatch_expose_explicit_snapshot(self):
        from solidworks_mcp import server
        schema=next(tool for tool in asyncio.run(server.list_tools()) if tool.name=='create_recovery_snapshot')
        self.assertEqual(schema.inputSchema['required'],['directory'])
        with patch.object(server.sw_automation,'create_recovery_snapshot',return_value={
            'success':True,'message':'snapshot','error_code':0,'error_name':'swSuccess'}) as save:
            reply=asyncio.run(server.call_tool('create_recovery_snapshot',{'directory':'C:/private/recovery'}))
            self.assertTrue(reply[0].text.startswith('[SUCCESS]'))
            save.assert_called_once_with('C:/private/recovery')
        self.assertIn('filepath',schema.inputSchema['properties'])
        with patch.object(server.sw_automation,'create_recovery_snapshot',return_value={
            'success':True,'message':'snapshot','error_code':0,'error_name':'swSuccess'}) as save:
            asyncio.run(server.call_tool('create_recovery_snapshot',{'directory':'C:/private/recovery','filepath':'C:/test.SLDPRT'}))
            save.assert_called_once_with('C:/private/recovery',filepath='C:/test.SLDPRT')
    def background_endpoint(self,document,requested=None):
        from types import SimpleNamespace
        app=SimpleNamespace(GetOpenDocumentByName=Mock(return_value=document))
        raw=SimpleNamespace(_oleobj_=object(),RevisionNumber='31.5')
        module=SimpleNamespace(ISldWorks=lambda obj:app,IModelDoc2=lambda obj:self.part)
        automation=SimpleNamespace(is_connected=True,_target_pid='123',_sw_app=raw,
            _result=lambda success,message,error_code=None,data=None:{'success':success,'message':message,'data':data})
        with patch('win32com.client.gencache.EnsureModule',return_value=module):
            return DocumentOperations.create_recovery_snapshot(automation,str(self.destination),
                filepath=requested if requested is not None else str(self.source)),app
    def test_background_endpoint_does_not_open_missing_source(self):
        result,app=self.background_endpoint(None)
        self.assertFalse(result['success']);self.assertIn('not open',result['message'])
        self.assertEqual(self.part.calls,[]);self.assertFalse(self.destination.exists())
        app.GetOpenDocumentByName.assert_called_once_with(str(self.source))
    def test_background_endpoint_rejects_package_types_without_saving(self):
        from types import SimpleNamespace
        self.part.GetType=2
        result,_=self.background_endpoint(SimpleNamespace(_oleobj_=object()))
        self.assertFalse(result['success']);self.assertIn('parts only',result['message'])
        self.assertEqual(self.part.calls,[])
    def test_background_endpoint_requires_absolute_matching_path(self):
        from types import SimpleNamespace
        result,app=self.background_endpoint(None,'relative.SLDPRT')
        self.assertFalse(result['success']);app.GetOpenDocumentByName.assert_not_called()
        result,_=self.background_endpoint(SimpleNamespace(_oleobj_=object()),str(self.root/'other.SLDPRT'))
        self.assertFalse(result['success']);self.assertIn('path mismatch',result['message'])
        self.assertEqual(self.part.calls,[])
