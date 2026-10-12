import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import Mock,patch
from solidworks_mcp.step_recovery import repair_step_links

class StepRepairTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.copy=self.root/'r-part.SLDPRT';self.step=self.root/'source.stp'
        self.copy.write_bytes(b'original private copy');self.step.write_bytes(b'saved step')
        self.source=SimpleNamespace(GetPathName='C:/working/source.SLDPRT',GetTitle='source',GetSaveFlag=True)
        self.app=SimpleNamespace(GetProcessID=123,ActiveDoc=self.source)
        self.app.GetOpenDocumentByName=Mock(return_value=None)
        self.bad_saved_link=False;self.saved=[]
        def deps(path,recursive,search,*args):
            private=search or Path(path)!=self.copy and not self.bad_saved_link
            return ['step',str(self.step) if private else 'C:/original/source.stp']
        self.app.GetDocumentDependencies2=deps
        def open_doc(path,*args):
            doc=SimpleNamespace(GetPathName=path,GetTitle=Path(path).name,GetSaveFlag=False)
            def save(path,version,flags):
                self.assertEqual(flags,3);Path(path).write_bytes(b'rewritten private copy');self.saved.append(path);return 0
            doc.SaveAs3=save;self.app.ActiveDoc=doc;return doc,0,0
        self.app.OpenDoc6=Mock(side_effect=open_doc)
        self.app.CloseDoc=Mock(side_effect=lambda title:setattr(self.app,'ActiveDoc',None))
        self.app.ActivateDoc3=Mock(side_effect=lambda *args:setattr(self.app,'ActiveDoc',self.source))
        self.mapping={'C:/source.SLDPRT':str(self.copy),'C:/source.stp':str(self.step)}
        for name,args in [('held_process',{'side_effect':lambda pid:nullcontext('start')}),
                          ('process_identity',{'return_value':'start'})]:
            p=patch('solidworks_mcp.step_recovery.'+name,**args);p.start();self.addCleanup(p.stop)
    def repair(self,**kwargs):
        return repair_step_links(self.app,123,self.root,self.mapping,lambda d:d,**kwargs)
    def test_readonly_private_copy_rewrites_and_restores_dirty_active_source(self):
        result=self.repair(allow_activation=True)
        self.assertEqual(len(result),1)
        self.assertEqual(self.copy.read_bytes(),b'rewritten private copy')
        self.assertIs(self.app.ActiveDoc,self.source);self.assertTrue(self.source.GetSaveFlag)
        self.app.OpenDoc6.assert_called_once_with(str(self.copy),1,3,'',0,0)
        self.assertFalse(Path(self.saved[0]).exists())
    def test_unresolved_private_step_does_not_open_any_document(self):
        self.app.GetDocumentDependencies2=lambda *args:['step','C:/original/source.stp']
        with self.assertRaisesRegex(RuntimeError,'resolve entirely'):self.repair(allow_activation=True)
        self.app.OpenDoc6.assert_not_called()
    def test_requires_activation_permission(self):
        with self.assertRaisesRegex(RuntimeError,'enabled temporary'):self.repair()
        self.app.OpenDoc6.assert_not_called()
    def test_private_document_already_open_is_not_taken_over(self):
        self.app.GetOpenDocumentByName.return_value=self.source
        with self.assertRaisesRegex(RuntimeError,'already open'):self.repair(allow_activation=True)
        self.app.OpenDoc6.assert_not_called()
    def test_invalid_saved_reference_does_not_replace_output(self):
        self.bad_saved_link=True
        with self.assertRaisesRegex(RuntimeError,'still refers outside'):self.repair(allow_activation=True)
        self.assertEqual(self.copy.read_bytes(),b'original private copy')
        self.assertIs(self.app.ActiveDoc,self.source)
    def test_output_escape_is_rejected(self):
        self.mapping['C:/source.stp']='C:/shared/source.stp'
        with self.assertRaisesRegex(ValueError,'must be private'):self.repair(allow_activation=True)
        self.app.OpenDoc6.assert_not_called()

if __name__=='__main__':unittest.main()
