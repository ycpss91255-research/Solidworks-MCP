import json,tempfile,unittest
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
from solidworks_mcp.assembly_recovery import snapshot_assembly,snapshot_package
from solidworks_mcp.recovery_snapshot import SnapshotError

class Doc:
    def __init__(self,path,kind):
        self.GetPathName=str(path);self.GetTitle=path.name;self.GetType=kind;self.GetSaveFlag=True
class App:
    GetProcessID=123
    def __init__(self,docs):self.docs=docs;self.ActiveDoc=docs[0]
    def GetOpenDocumentByName(self,path):return next((d for d in self.docs if d.GetPathName==path),None)
    def GetDocumentDependencies2(self,*args):return []
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
    def test_background_package_preserves_active_document(self):
        root=self.app.docs[0];self.app.ActiveDoc=self.app.docs[1]
        result=snapshot_package(self.app,123,self.directory,pack_factory=lambda doc:self.pack,document=root)
        self.assertEqual(result['active_before'],result['active_after'])
        self.assertIs(self.app.ActiveDoc,self.app.docs[1]);self.assertEqual(result['status'],'complete')
    def test_background_package_focus_change_is_failed(self):
        root=self.app.docs[0];self.app.ActiveDoc=self.app.docs[1]
        self.pack.action=lambda:setattr(self.app,'ActiveDoc',root)
        with self.assertRaisesRegex(SnapshotError,'Active document changed'):
            snapshot_package(self.app,123,self.directory,pack_factory=lambda doc:self.pack,document=root)
    def test_missing_and_relative_sources_cannot_save(self):
        for invalid in (str(self.root/'nested.SLDASM'),str(self.root/'missing.SLDPRT'),'relative.SLDPRT'):
            with self.subTest(invalid=invalid):
                self.pack.paths=[str(self.assembly),invalid]
                with self.assertRaises(ValueError):self.snapshot()
                self.assertEqual(self.pack.saved,0)
    def test_saved_nested_assembly_is_copied_and_its_source_preserved(self):
        nested=self.root/'nested.SLDASM';nested.write_bytes(b'saved child assembly')
        self.app.docs.append(Doc(nested,2));self.pack.paths.append(str(nested))
        result=self.snapshot()
        self.assertEqual(len(result['package_files']),3)
        self.assertEqual(nested.read_bytes(),b'saved child assembly')
        self.assertTrue(self.app.docs[-1].GetSaveFlag)
    def test_existing_non_cad_dependency_is_rejected_before_save(self):
        dependency=self.root/'linked.txt';dependency.write_bytes(b'external data')
        self.pack.paths.append(str(dependency))
        with self.assertRaisesRegex(ValueError,'part and assembly references'):self.snapshot()
        self.assertEqual(self.pack.saved,0)
    def test_step_dependencies_are_complete_byte_identical_private_copies(self):
        step=self.root/'sensor.stp';step.write_bytes(b'ISO-10303-21; geometry')
        self.pack.paths.append(str(step))
        self.pack.action=lambda:Path(self.pack.outputs[-1]).write_bytes(step.read_bytes())
        result=self.snapshot()
        self.assertEqual(result['step_source_files'],[str(step)])
        self.assertEqual(Path(result['package_files'][str(step)]).read_bytes(),step.read_bytes())
        self.assertTrue(result['source_preserved'])
    def test_modified_step_copy_is_rejected(self):
        step=self.root/'sensor.step';step.write_bytes(b'original neutral geometry')
        self.pack.paths.append(str(step))
        with self.assertRaisesRegex(SnapshotError,'STEP dependency copy'):self.snapshot()
    def test_original_step_link_prevents_complete_recovery_claim(self):
        step=self.root/'sensor.stp';step.write_bytes(b'neutral source')
        self.pack.paths.append(str(step))
        self.pack.action=lambda:Path(self.pack.outputs[-1]).write_bytes(step.read_bytes())
        self.app.GetDocumentDependencies2=lambda *args:['sensor',str(step)]
        with self.assertRaisesRegex(SnapshotError,'STEP references still point outside') as result:self.snapshot()
        self.assertTrue(result.exception.data['unresolved_step_references'])
    def test_enabled_step_repair_is_rechecked_before_completion(self):
        step=self.root/'sensor.stp';step.write_bytes(b'neutral source')
        self.pack.paths.append(str(step))
        self.pack.action=lambda:Path(self.pack.outputs[-1]).write_bytes(step.read_bytes())
        self.app.GetDocumentDependencies2=lambda *args:['sensor',str(step)]
        def repair(*args,**kwargs):
            self.assertTrue(kwargs['allow_activation'])
            self.app.GetDocumentDependencies2=lambda *args:['sensor',self.pack.outputs[-1]]
            return [{'document':self.pack.outputs[1]}]
        with patch('solidworks_mcp.step_recovery.repair_step_links',side_effect=repair):
            result=snapshot_package(self.app,123,self.directory,pack_factory=lambda d:self.pack,
                                    allow_step_activation=True)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['unresolved_step_references'],[])
        self.assertTrue(result['step_reference_repairs'])
    def test_attempted_step_repair_cannot_bypass_unresolved_reference_guard(self):
        step=self.root/'sensor.stp';step.write_bytes(b'neutral source')
        self.pack.paths.append(str(step))
        self.pack.action=lambda:Path(self.pack.outputs[-1]).write_bytes(step.read_bytes())
        self.app.GetDocumentDependencies2=lambda *args:['sensor',str(step)]
        with patch('solidworks_mcp.step_recovery.repair_step_links',return_value=[]):
            with self.assertRaisesRegex(SnapshotError,'STEP references still point outside'):
                snapshot_package(self.app,123,self.directory,pack_factory=lambda d:self.pack,
                                 allow_step_activation=True)
    def test_native_only_statuses_still_require_every_step_file(self):
        step=self.root/'sensor.stp';step.write_bytes(b'neutral source')
        self.pack.paths.append(str(step))
        original=self.pack.save
        def save():
            result=original();Path(self.pack.outputs[-1]).write_bytes(step.read_bytes())
            return result[:-1]
        self.pack.save=save
        result=self.snapshot()
        self.assertEqual(result['save_status_count'],2)
        self.assertEqual(len(result['package_files']),3)
        def missing():
            result=save();Path(self.pack.outputs[-1]).unlink();return result
        self.pack.save=missing
        with self.assertRaisesRegex(SnapshotError,'output is missing'):self.snapshot()
    def test_dirty_loaded_step_does_not_claim_saved_baseline_is_recovery(self):
        step=self.root/'sensor.stp';step.write_bytes(b'neutral baseline')
        self.pack.paths.append(str(step));self.app.docs.append(Doc(step,1))
        with self.assertRaisesRegex(ValueError,'Dirty STEP'):self.snapshot()
        self.assertEqual(self.pack.saved,0)
    def test_drawing_package_preserves_drawing_and_model_sources(self):
        drawing=self.root/'source.SLDDRW';drawing.write_bytes(b'saved drawing')
        self.app.docs[0]=Doc(drawing,3);self.app.ActiveDoc=self.app.docs[0]
        self.pack.paths=[str(drawing),str(self.part)]
        result=snapshot_package(self.app,123,self.directory,pack_factory=lambda doc:self.pack)
        self.assertEqual(result['document_type'],'drawing');self.assertEqual(result['status'],'complete')
        self.assertEqual(drawing.read_bytes(),b'saved drawing')
        self.assertEqual(self.part.read_bytes(),b'saved 5 mm part')
        self.assertTrue(all(d.GetSaveFlag for d in self.app.docs))
    def test_assembly_specific_wrapper_refuses_drawing(self):
        self.app.docs[0].GetType=3
        with self.assertRaisesRegex(ValueError,'supported assembly or drawing'):self.snapshot()
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
    def test_occurrence_state_is_recorded_and_rechecked(self):
        state={'configuration':'MR12','occurrences':[{'source_path':str(self.part),'suppressed':True}]}
        result=snapshot_package(self.app,123,self.directory,pack_factory=lambda d:self.pack,
                                state_reader=lambda d:state)
        self.assertEqual(result['assembly_occurrence_state'],state)
        self.assertEqual(result['assembly_occurrence_state_after'],state)
    def test_suppression_change_cannot_be_hidden_by_unchanged_dirty_flag(self):
        states=iter([{'configuration':'MR12','occurrences':[{'suppressed':True}]},
                     {'configuration':'MR12','occurrences':[{'suppressed':False}]}])
        with self.assertRaisesRegex(SnapshotError,'suppression changed') as caught:
            snapshot_package(self.app,123,self.directory,pack_factory=lambda d:self.pack,
                             state_reader=lambda d:next(states))
        self.assertEqual(caught.exception.data['status'],'failed')
    def test_target_reuse_cannot_save(self):
        with patch('solidworks_mcp.assembly_recovery.process_identity',return_value='different'):
            with self.assertRaisesRegex(SnapshotError,'identity changed'):self.snapshot()
        self.assertEqual(self.pack.saved,0)

if __name__=='__main__':unittest.main()
