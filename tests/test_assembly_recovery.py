import json,tempfile,unittest
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
from solidworks_mcp.assembly_recovery import snapshot_assembly
from solidworks_mcp.recovery_snapshot import SnapshotError

class Doc:
    def __init__(self,path,kind):
        self.GetPathName=str(path);self.GetTitle=path.name;self.GetType=kind;self.GetSaveFlag=True
class App:
    GetProcessID=123
    def __init__(self,docs):self.docs=docs;self.ActiveDoc=docs[0]
    def GetOpenDocumentByName(self,path):return next((d for d in self.docs if d.GetPathName==path),None)
class Pack:
    def __init__(self,app):self.app=app;self.paths=[d.GetPathName for d in app.docs];self.saved=0;self.action=None
    def documents(self):return self.paths
    def destinations(self,directory,prefix):
        self.outputs=[str(directory/(prefix+Path(p).name)) for p in self.paths]
        return self.outputs
    def save(self):
        self.saved+=1
        for path in self.outputs:Path(path).write_bytes(b'private native copy')
        if self.action:self.action()
        return [0]*len(self.paths)

class AssemblyRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.assembly=self.root/'source.SLDASM';self.part=self.root/'part.SLDPRT'
        self.assembly.write_bytes(b'saved assembly');self.part.write_bytes(b'saved 5 mm part')
        self.app=App([Doc(self.assembly,2),Doc(self.part,1)]);self.pack=Pack(self.app)
        self.directory=self.root/'recovery'
        for name,kwargs in [('held_process',{'side_effect':lambda pid:nullcontext('start')}),
                            ('process_identity',{'return_value':'start'})]:
            p=patch('solidworks_mcp.assembly_recovery.'+name,**kwargs);p.start();self.addCleanup(p.stop)
    def snapshot(self):return snapshot_assembly(self.app,123,self.directory,pack_factory=lambda d:self.pack)
    def test_private_package_preserves_both_sources(self):
        result=self.snapshot()
        self.assertEqual(result['status'],'complete');self.assertEqual(self.pack.saved,1)
        self.assertEqual(self.assembly.read_bytes(),b'saved assembly');self.assertEqual(self.part.read_bytes(),b'saved 5 mm part')
        self.assertTrue(all(d.GetSaveFlag for d in self.app.docs))
        self.assertEqual(len(result['package_files']),2)
        self.assertEqual(json.loads(Path(result['manifest_path']).read_text())['status'],'complete')
    def test_wrong_pid_cannot_create_files_or_save(self):
        self.app.GetProcessID=456
        with self.assertRaisesRegex(ValueError,'configured PID'):self.snapshot()
        self.assertFalse(self.directory.exists());self.assertEqual(self.pack.saved,0)
    def test_nested_missing_and_relative_sources_cannot_save(self):
        for invalid in (str(self.root/'nested.SLDASM'),str(self.root/'missing.SLDPRT'),'relative.SLDPRT'):
            with self.subTest(invalid=invalid):
                self.pack.paths=[str(self.assembly),invalid]
                with self.assertRaises(ValueError):self.snapshot()
                self.assertEqual(self.pack.saved,0)
    def test_destination_escape_is_rejected_before_save(self):
        self.pack.destinations=lambda directory,prefix:[str(directory/'copy.SLDASM'),str(self.root/'escape.SLDPRT')]
        with self.assertRaisesRegex(SnapshotError,'new private'):self.snapshot()
        self.assertEqual(self.pack.saved,0);self.assertFalse((self.root/'escape.SLDPRT').exists())
    def test_disk_or_loaded_state_changes_cannot_be_success(self):
        for action in (lambda:self.part.write_bytes(b'changed'),lambda:setattr(self.app.docs[1],'GetSaveFlag',False)):
            with self.subTest(action=action):
                self.pack.action=action
                with self.assertRaisesRegex(SnapshotError,'Source state or disk files changed') as caught:self.snapshot()
                self.assertEqual(caught.exception.data['status'],'failed')
                self.part.write_bytes(b'saved 5 mm part');self.app.docs[1].GetSaveFlag=True
    def test_target_reuse_cannot_save(self):
        with patch('solidworks_mcp.assembly_recovery.process_identity',return_value='different'):
            with self.assertRaisesRegex(SnapshotError,'identity changed'):self.snapshot()
        self.assertEqual(self.pack.saved,0)

if __name__=='__main__':unittest.main()
