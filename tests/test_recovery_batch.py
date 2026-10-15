import unittest
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import Mock,patch
from solidworks_mcp.recovery_batch import snapshot_documents

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.original=SimpleNamespace(GetPathName='C:/view.SLDDRW',GetTitle='view',GetSaveFlag=True,GetType=3)
        self.part=SimpleNamespace(GetPathName='C:/part.SLDPRT',GetTitle='part',GetSaveFlag=True,GetType=1)
        self.assembly=SimpleNamespace(GetPathName='C:/assembly.SLDASM',GetTitle='assembly',GetSaveFlag=True,GetType=2)
        self.external=SimpleNamespace(GetPathName='C:/other.SLDPRT',GetTitle='other',GetSaveFlag=True,GetType=1)
        self.app=SimpleNamespace(GetProcessID=123,ActiveDoc=self.original);self.calls=[]
        def activate(title,preferences,option,errors):
            self.calls.append((title,preferences,option))
            self.app.ActiveDoc=next(d for d in (self.original,self.part,self.assembly,self.external) if d.GetTitle==title)
        self.app.ActivateDoc3=activate
        self.complete={'status':'complete','pid':123,'process_start_time':'start'}
        for name,args in [('held_process',{'side_effect':lambda pid:nullcontext('start')}),('process_identity',{'return_value':'start'}),
                          ('snapshot_part',{'return_value':dict(self.complete)}),('snapshot_package',{'return_value':dict(self.complete)})]:
            patcher=patch('solidworks_mcp.recovery_batch.'+name,**args);patcher.start();self.addCleanup(patcher.stop)
    def run_batch(self,documents=None,**kwargs):
        return snapshot_documents(self.app,123,'C:/private',documents or [self.part,self.assembly],lambda d:d,**kwargs)
    def test_mixed_batch_restores_view_and_preserves_every_copy(self):
        result=self.run_batch(allow_activation=True)
        self.assertTrue(result['success']);self.assertEqual(len(result['data']['snapshots']),2)
        self.assertIs(self.app.ActiveDoc,self.original)
        self.assertEqual(self.calls,[('assembly',False,1),('view',False,1)])
    def test_part_only_batch_never_activates_a_document(self):
        result=self.run_batch([self.part])
        self.assertTrue(result['success']);self.assertEqual(self.calls,[])
    def test_background_activation_requires_explicit_setting(self):
        result=self.run_batch([self.assembly])
        self.assertFalse(result['success']);self.assertEqual(self.calls,[])
    def test_package_failure_restores_view_and_retains_completed_part(self):
        with patch('solidworks_mcp.recovery_batch.snapshot_package',side_effect=RuntimeError('copy failed')):
            result=self.run_batch(allow_activation=True)
        self.assertFalse(result['success']);self.assertEqual(len(result['data']['snapshots']),1)
        self.assertIs(self.app.ActiveDoc,self.original)
    def test_external_view_change_is_not_overridden(self):
        def package(*args,**kwargs):self.app.ActiveDoc=self.external;return dict(self.complete)
        with patch('solidworks_mcp.recovery_batch.snapshot_package',side_effect=package):
            result=self.run_batch([self.assembly],allow_activation=True)
        self.assertFalse(result['success']);self.assertIs(self.app.ActiveDoc,self.external)
        self.assertEqual(len(self.calls),1)
    def test_busy_command_prevents_any_copy_or_activation(self):
        result=self.run_batch(allow_activation=True,idle=lambda:False)
        self.assertFalse(result['success']);self.assertEqual(result['data']['snapshots'],[]);self.assertEqual(self.calls,[])
    def test_foreign_snapshot_cannot_complete_batch(self):
        with patch('solidworks_mcp.recovery_batch.snapshot_part',return_value={'status':'complete','pid':999,'process_start_time':'start'}):
            result=self.run_batch([self.part])
        self.assertFalse(result['success']);self.assertEqual(result['data']['snapshots'],[])
    def test_pid_change_does_not_force_view_restore_on_another_target(self):
        def package(*args,**kwargs):self.app.GetProcessID=999;return dict(self.complete)
        with patch('solidworks_mcp.recovery_batch.snapshot_package',side_effect=package):
            result=self.run_batch([self.assembly],allow_activation=True)
        self.assertFalse(result['success']);self.assertEqual(len(self.calls),1)

    def test_native_package_fault_skips_all_cad_cleanup_and_persists_identity(self):
        import pywintypes
        from solidworks_mcp.recovery_snapshot import SnapshotError
        for wrapped in (False,True):
            with self.subTest(wrapped=wrapped):
                self.app.ActiveDoc=self.original;self.calls=[]
                self.app.GetProcessID=Mock(spec=[],return_value=123);at_fault=[]
                native=pywintypes.com_error(-2147417851,'native fault',None,None)
                error=SnapshotError('wrapped native fault',{}) if wrapped else native
                if wrapped:error.__cause__=native
                def package(*args,**kwargs):
                    at_fault.append(self.app.GetProcessID.call_count)
                    raise error
                with patch('solidworks_mcp.recovery_batch.snapshot_package',side_effect=package), \
                     patch('solidworks_mcp.native_fault.FaultStore.record',return_value={'pid':123,'hresult':-2147417851}) as record:
                    result=self.run_batch(allow_activation=True)
                self.assertFalse(result['success'])
                self.assertEqual(self.app.GetProcessID.call_count,at_fault[0])
                self.assertEqual(self.calls,[('assembly',False,1)])
                self.assertEqual(result['data']['native_fault']['hresult'],-2147417851)
                record.assert_called_once_with(123,'start',error)

if __name__=='__main__':unittest.main()
