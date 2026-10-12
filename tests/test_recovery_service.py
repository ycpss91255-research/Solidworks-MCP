import json,os,sys,tempfile,unittest
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
from solidworks_mcp.recovery_service import ensure_recovery_worker,recovery_worker_error

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
                     'worker_start_time':'worker-start','status':'starting',
                     'settings':{'interval_seconds':60.0,'assemblies':False,'drawings':False,
                                 'all_documents':False,'background_activation':False}}
    def invoke(self,identity=None,launcher=None,app=None):
        with patch.dict(os.environ,self.environment,clear=True), \
             patch('solidworks_mcp.recovery_service.process_identity',return_value='cad-start'), \
             patch('solidworks_mcp.recovery_service.monitor_lock',return_value=nullcontext()), \
             patch('solidworks_mcp.recovery_service.worker_identity',return_value=identity), \
             patch('solidworks_mcp.recovery_service.start_desktop_process',side_effect=launcher) as launch:
            result=ensure_recovery_worker(123,app=app)
            return result,launch.call_count
    def test_disabled_has_no_process_or_file_side_effect(self):
        with patch.dict(os.environ,{},clear=True),patch('solidworks_mcp.recovery_service.start_desktop_process') as launch:
            self.assertIsNone(ensure_recovery_worker(123));launch.assert_not_called()
    def health(self,identity='live',policy=None):
        self.status.write_text(json.dumps(self.record))
        actual=(str(Path(sys._base_executable).resolve()).casefold(),'worker-start') if identity=='live' else identity
        with patch('solidworks_mcp.recovery_service.process_identity',return_value='cad-start'), \
             patch('solidworks_mcp.recovery_service.worker_identity',return_value=actual), \
             patch('solidworks_mcp.recovery_service.start_desktop_process') as launch:
            error=recovery_worker_error(123,{'worker_pid':456,'worker_start_time':'worker-start','policy':policy,
                                            'process_start_time':'cad-start','status_file':str(self.status),
                                            'settings':{'interval_seconds':60.0,'assemblies':False,'drawings':False,
                                                        'all_documents':False,'background_activation':False}})
            launch.assert_not_called()
            return error
    def test_running_worker_health_is_verified(self):
        self.assertIsNone(self.health())
    def test_native_interval_update_is_healthy_but_scope_update_is_not(self):
        self.record['follow_native_preferences']=True
        self.record['settings']['interval_seconds']=120
        self.assertIsNone(self.health(policy={'source':'solidworks'}))
        self.record['settings']['assemblies']=True
        self.assertIn('settings changed',self.health(policy={'source':'solidworks'}))
    def test_old_native_policy_worker_requires_normal_stop(self):
        self.assertIn('does not follow native preferences',self.health(policy={'source':'solidworks'}))
    def test_unsupported_dirty_documents_are_not_silently_claimed_protected(self):
        self.record['unprotected_documents']=[{'path':'C:/drawing.SLDDRW','title':'drawing'}]
        self.assertIn('unsupported dirty documents',self.health())
    def test_failure_after_start_is_reported_even_if_process_still_live(self):
        self.record.update(status='failed',error='Save failed')
        self.assertIn('Save failed',self.health())
    def test_user_stopped_worker_is_reported(self):
        self.record.update(status='stopped',reason='stop_requested')
        self.assertIn('stop_requested',self.health(None))
    def test_worker_exit_without_terminal_status_is_reported(self):
        self.assertIn('exited',self.health(None))
    def test_reused_worker_pid_is_not_treated_as_healthy(self):
        self.assertIn('identity changed',self.health(('foreign.exe','new-start')))
    def test_other_worker_status_is_not_adopted(self):
        self.record['worker_pid']=789
        self.assertIn('identity changed',self.health())
    def test_rewritten_status_cannot_adopt_reused_worker_pid(self):
        self.record['worker_start_time']='replacement-start'
        self.assertIn('identity changed',self.health())
    def test_same_live_worker_reused_after_mcp_restart(self):
        self.status.write_text(json.dumps(self.record))
        result,count=self.invoke((str(Path(sys._base_executable).resolve()).casefold(),'worker-start'))
        self.assertTrue(result['reused']);self.assertEqual(count,0)
    def test_old_worker_cannot_claim_new_all_document_settings(self):
        self.status.write_text(json.dumps(self.record));self.environment['SOLIDWORKS_RECOVERY_ALL_DOCUMENTS']='1'
        with patch.dict(os.environ,self.environment,clear=True), \
             patch('solidworks_mcp.recovery_service.process_identity',return_value='cad-start'), \
             patch('solidworks_mcp.recovery_service.monitor_lock',return_value=nullcontext()), \
             patch('solidworks_mcp.recovery_service.worker_identity',return_value=(str(Path(sys._base_executable).resolve()).casefold(),'worker-start')), \
             patch('solidworks_mcp.recovery_service.start_desktop_process') as launch:
            with self.assertRaisesRegex(RuntimeError,'settings differ'):ensure_recovery_worker(123)
            launch.assert_not_called()
    def test_worker_without_settings_is_not_silently_reused(self):
        del self.record['settings'];self.status.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(RuntimeError,'unverified'):
            self.invoke((str(Path(sys._base_executable).resolve()).casefold(),'worker-start'))
    def test_health_reports_rewritten_worker_settings(self):
        self.record['settings']['all_documents']=True
        self.assertIn('settings changed',self.health())
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
            self.record['startup_token']=arguments[arguments.index('--startup-token')+1]
            self.status.write_text(json.dumps(self.record));return 999  # venv launcher PID differs from actual worker
        result,count=self.invoke((str(Path(sys._base_executable).resolve()).casefold(),'worker-start'),launcher=launch)
        self.assertFalse(result['reused']);self.assertEqual(count,1)
        self.assertEqual(result['worker_pid'],456)
        self.assertFalse((self.root/'worker-startup.json').exists())
    def test_native_policy_launch_requests_preference_tracking(self):
        self.environment['SOLIDWORKS_RECOVERY_MONITOR']='auto'
        policy={'enabled':True,'source':'solidworks','directory':str(self.root),
                'settings':self.record['settings'],'preferences':{'auto_recover_enabled':True}}
        def launch(executable,cwd,arguments):
            self.assertIn('--follow-native-preferences',arguments)
            self.record.update(startup_token=arguments[arguments.index('--startup-token')+1],
                               follow_native_preferences=True)
            self.status.write_text(json.dumps(self.record));return 999
        with patch('solidworks_mcp.recovery_policy.automatic_policy',return_value=policy):
            result,count=self.invoke((str(Path(sys._base_executable).resolve()).casefold(),'worker-start'),
                                     launcher=launch,app=object())
        self.assertEqual(count,1);self.assertFalse(result['reused'])
    def reserve(self):
        pending={'kind':'recovery_worker_startup','pid':123,'process_start_time':'cad-start',
                 'session_file':str(self.session.resolve()),'startup_token':'reserved'}
        (self.root/'worker-startup.json').write_text(json.dumps(pending))
    def test_unconfirmed_reservation_prevents_duplicate_even_if_launcher_exited(self):
        self.reserve()
        with self.assertRaisesRegex(RuntimeError,'unconfirmed'):self.invoke(None)
        self.assertTrue((self.root/'worker-startup.json').exists())
    def test_old_status_cannot_release_unconfirmed_reservation(self):
        self.reserve();self.record['startup_token']='old'
        self.status.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(RuntimeError,'unconfirmed'):
            self.invoke((str(Path(sys._base_executable).resolve()).casefold(),'worker-start'))
    def test_delayed_worker_status_reuses_original_attempt(self):
        self.reserve();self.record['startup_token']='reserved'
        self.status.write_text(json.dumps(self.record))
        result,count=self.invoke((str(Path(sys._base_executable).resolve()).casefold(),'worker-start'))
        self.assertTrue(result['reused']);self.assertEqual(count,0)
        self.assertFalse((self.root/'worker-startup.json').exists())
    def test_observation_timeout_then_reconnect_does_not_launch_again(self):
        with patch('solidworks_mcp.recovery_service.time.monotonic',side_effect=[0,11]):
            with self.assertRaisesRegex(RuntimeError,'observation timed out'):
                self.invoke(None,launcher=lambda *args:999)
        self.assertTrue((self.root/'worker-startup.json').exists())
        with patch.dict(os.environ,self.environment,clear=True), \
             patch('solidworks_mcp.recovery_service.process_identity',return_value='cad-start'), \
             patch('solidworks_mcp.recovery_service.monitor_lock',return_value=nullcontext()), \
             patch('solidworks_mcp.recovery_service.start_desktop_process') as launch:
            with self.assertRaisesRegex(RuntimeError,'unconfirmed'):ensure_recovery_worker(123)
            launch.assert_not_called()
    def test_other_target_reservation_is_not_replaced(self):
        self.reserve();self.session.write_text(json.dumps({'pid':123,'start_time':'changed'}))
        with patch.dict(os.environ,self.environment,clear=True), \
             patch('solidworks_mcp.recovery_service.process_identity',return_value='changed'), \
             patch('solidworks_mcp.recovery_service.monitor_lock',return_value=nullcontext()), \
             patch('solidworks_mcp.recovery_service.start_desktop_process') as launch:
            with self.assertRaisesRegex(RuntimeError,'reservation identity mismatch'):
                ensure_recovery_worker(123)
            launch.assert_not_called()
    def test_terminal_but_still_live_worker_is_not_reported_as_running(self):
        self.record['status']='failed';self.status.write_text(json.dumps(self.record))
        with self.assertRaisesRegex(RuntimeError,'finishing shutdown'):
            self.invoke((str(Path(sys._base_executable).resolve()).casefold(),'worker-start'))
    def test_launch_failure_is_explicit(self):
        def launch(*args):raise RuntimeError('Desktop unavailable')
        with self.assertRaisesRegex(RuntimeError,'Desktop unavailable'):self.invoke(launcher=launch)
    def test_unrelated_status_not_overwritten(self):
        self.status.write_text('{"kind":"user-data"}')
        with self.assertRaisesRegex(ValueError,'unrelated'):self.invoke()
        self.assertEqual(self.status.read_text(),'{"kind":"user-data"}')

if __name__=='__main__':unittest.main()
