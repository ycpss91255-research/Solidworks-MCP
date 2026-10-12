import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from solidworks_mcp.package_repair_service import configured_processor
from solidworks_mcp.recovery_snapshot import fingerprint

class RepairServiceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.generation=self.root/'generation';self.generation.mkdir()
        self.source=self.root/'source-session.json';self.helper=self.root/'helper-session.json'
        self.source.write_text(json.dumps({'pid':123,'start_time':'source-start'}))
        self.owner={'pid':456,'start_time':'helper-start','role':'recovery_repair',
                    'source_session_file':str(self.source.resolve())}
        self.helper.write_text(json.dumps(self.owner))
        src=self.root/'source.SLDASM';src.write_bytes(b'source');dst=self.generation/'copy.SLDASM';dst.write_bytes(b'copy')
        self.evidence={'pid':123,'process_start_time':'source-start','manifest_path':str(self.generation/'manifest.json'),
                       'snapshot_path':str(dst),'package_files':{str(src):str(dst)},
                       'source_files_sha256':{str(src):fingerprint(str(src))},
                       'assembly_occurrence_state':{'configuration':'MR12','occurrences':[]}}
        self.env={'SOLIDWORKS_SESSION_FILE':str(self.source),'SOLIDWORKS_RECOVERY_REPAIR_SESSION_FILE':str(self.helper)}
    def test_no_config_has_no_worker_side_effect(self):
        with patch('solidworks_mcp.package_repair_service.start_desktop_process') as run:
            self.assertIsNone(configured_processor({}));run.assert_not_called()
    def test_source_session_cannot_be_its_own_helper(self):
        with self.assertRaisesRegex(ValueError,'separate'):
            configured_processor(dict(self.env,SOLIDWORKS_RECOVERY_REPAIR_SESSION_FILE=str(self.source)))
    def test_absent_helper_does_not_launch_cad_or_worker(self):
        with patch('solidworks_mcp.package_repair_service.process_identity',return_value=None), \
             patch('solidworks_mcp.package_repair_service.start_desktop_process') as run:
            with self.assertRaisesRegex(RuntimeError,'absent'):configured_processor(self.env)(self.evidence)
            run.assert_not_called()
    def test_foreign_owner_is_rejected(self):
        self.owner['source_session_file']=str(self.root/'other.json');self.helper.write_text(json.dumps(self.owner))
        with patch('solidworks_mcp.package_repair_service.start_desktop_process') as run:
            with self.assertRaisesRegex(RuntimeError,'owned'):configured_processor(self.env)(self.evidence)
            run.assert_not_called()
    def test_correlated_worker_result_is_validated_and_helper_autolaunch_is_disabled(self):
        def run(executable,cwd,argv):
            self.assertEqual(executable,sys.executable)
            self.assertIn('--configure-helper-environment',argv)
            request=json.loads(Path(argv[argv.index('--request')+1]).read_text())
            result={'token':request['token'],'status':'repaired','helper_pid':456,'helper_start_time':'helper-start',
                    'assembly_state_restoration':{'verified_occurrences':0},'reopen_errors':0,'step_aliases':{},
                    'package_files_sha256':{p:fingerprint(p) for p in self.evidence['package_files'].values()}}
            Path(argv[argv.index('--response')+1]).write_text(json.dumps(result));return 999
        with patch('solidworks_mcp.package_repair_service.process_identity',return_value='helper-start'), \
             patch('solidworks_mcp.package_repair_service.start_desktop_process',side_effect=run):
            self.assertEqual(configured_processor(self.env)(self.evidence)['helper_pid'],456)

if __name__=='__main__':unittest.main()
