import json,os,sys,tempfile,unittest
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
from solidworks_mcp.recovery_service import ensure_recovery_worker

class RecoveryServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.session=self.root/'session.json'
        self.session.write_text(json.dumps({'pid':123,'start_time':'cad-start'}))
        self.status=self.root/'monitor.json'
        self.environment={'SOLIDWORKS_RECOVERY_MONITOR':'1','SOLIDWORKS_SESSION_FILE':str(self.session),
                          'SOLIDWORKS_RECOVERY_DIRECTORY':str(self.root)}
        self.record={'kind':'part_recovery_monitor','session_file':str(self.session.resolve()),
                     'pid':123,'process_start_time':'cad-start','worker_pid':456,
                     'worker_start_time':'worker-start','status':'starting'}
    def invoke(self,identity=None,launcher=None):
        with patch.dict(os.environ,self.environment,clear=True), \
             patch('solidworks_mcp.recovery_service.process_identity',return_value='cad-start'), \
             patch('solidworks_mcp.recovery_service.monitor_lock',return_value=nullcontext()), \
             patch('solidworks_mcp.recovery_service.worker_identity',return_value=identity), \
             patch('solidworks_mcp.recovery_service.start_desktop_process',side_effect=launcher) as launch:
            result=ensure_recovery_worker(123)
            return result,launch.call_count
    def test_disabled_has_no_process_or_file_side_effect(self):
        with patch.dict(os.environ,{},clear=True),patch('solidworks_mcp.recovery_service.start_desktop_process') as launch:
            self.assertIsNone(ensure_recovery_worker(123));launch.assert_not_called()
    def test_same_live_worker_reused_after_mcp_restart(self):
        self.status.write_text(json.dumps(self.record))
        result,count=self.invoke((str(Path(sys.executable).resolve()).casefold(),'worker-start'))
        self.assertTrue(result['reused']);self.assertEqual(count,0)
    def test_reused_worker_pid_refuses_duplicate(self):
        self.status.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(RuntimeError,'identity mismatch'):
            self.invoke(('foreign.exe','other-start'))
    def test_other_cad_target_cannot_start_monitor(self):
        self.session.write_text(json.dumps({'pid':999,'start_time':'cad-start'}))
        with self.assertRaisesRegex(RuntimeError,'does not own'):self.invoke()
    def test_stop_marker_is_respected(self):
        (self.root/'requested.stop').touch()
        with self.assertRaisesRegex(RuntimeError,'stop marker'):self.invoke()
    def test_launch_reports_child_status_and_passes_private_paths(self):
        def launch(executable,cwd,arguments):
            self.assertEqual(executable,sys.executable)
            self.assertIn(str(self.session),arguments);self.assertIn(str(self.status),arguments)
            self.status.write_text(json.dumps(self.record));return 456
        result,count=self.invoke(launcher=launch)
        self.assertFalse(result['reused']);self.assertEqual(count,1)
    def test_launch_failure_is_explicit(self):
        def launch(*args):raise RuntimeError('Desktop unavailable')
        with self.assertRaisesRegex(RuntimeError,'Desktop unavailable'):self.invoke(launcher=launch)
    def test_unrelated_status_not_overwritten(self):
        self.status.write_text('{"kind":"user-data"}')
        with self.assertRaisesRegex(ValueError,'unrelated'):self.invoke()
        self.assertEqual(self.status.read_text(),'{"kind":"user-data"}')

if __name__=='__main__':unittest.main()
