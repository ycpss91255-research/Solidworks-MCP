import unittest
from unittest.mock import Mock,patch
from solidworks_mcp.recovery_policy import automatic_policy
from solidworks_mcp.recovery_service import ensure_recovery_worker,matching_settings

class RecoveryPolicyTests(unittest.TestCase):
    def app(self,auto=True,backup=False,minutes=5,mode=2,pid=123):
        a=Mock();a.GetProcessID=pid
        a.GetUserPreferenceToggle.side_effect=lambda n:{319:auto,320:backup}[n]
        a.GetUserPreferenceIntegerValue.side_effect=lambda n:{3:minutes,301:mode}[n]
        return a
    def env(self):return {'SOLIDWORKS_SESSION_FILE':'C:/work/.codex/session.json'}
    def test_default_follows_enabled_autorecover_and_interval(self):
        p=automatic_policy(self.app(),123,self.env())
        self.assertTrue(p['enabled']);self.assertEqual(p['settings']['interval_seconds'],300)
        self.assertTrue(all(p['settings'][k] for k in ('assemblies','drawings','all_documents','background_activation')))
        self.assertEqual(p['directory'],'C:\\work\\.codex\\recovery\\session')
    def test_both_disabled_never_launches(self):
        a=self.app(False,False)
        with patch.dict('os.environ',{},clear=True),patch('solidworks_mcp.recovery_service.start_desktop_process') as launch:
            self.assertIsNone(ensure_recovery_worker(123,app=a));launch.assert_not_called()
        a.GetUserPreferenceIntegerValue.assert_not_called()
    def test_backup_only_starts_supplemental_recovery(self):
        p=automatic_policy(self.app(False,True),123,self.env())
        self.assertTrue(p['enabled']);self.assertFalse(p['preferences']['auto_recover_enabled'])
    def test_explicit_disable_does_not_even_read_cad_settings(self):
        a=Mock()
        with patch.dict('os.environ',{'SOLIDWORKS_RECOVERY_MONITOR':'0'},clear=True):
            self.assertIsNone(ensure_recovery_worker(123,app=a))
        a.GetUserPreferenceToggle.assert_not_called()
    def test_cannot_read_another_pid(self):
        a=self.app(pid=456)
        with self.assertRaisesRegex(RuntimeError,'PID mismatch'):automatic_policy(a,123,self.env())
        a.GetUserPreferenceToggle.assert_not_called()
    def test_change_count_is_not_misinterpreted_as_minutes(self):
        with self.assertRaisesRegex(ValueError,'minute interval'):automatic_policy(self.app(mode=1),123,self.env())
    def test_interval_override_handles_change_count_explicitly(self):
        e=dict(self.env(),SOLIDWORKS_RECOVERY_INTERVAL='120')
        self.assertEqual(automatic_policy(self.app(mode=1),123,e)['settings']['interval_seconds'],120)
    def test_failed_preference_read_is_not_treated_as_disabled(self):
        a=self.app();a.GetUserPreferenceToggle.side_effect=RuntimeError('COM busy')
        with self.assertRaisesRegex(RuntimeError,'COM busy'):automatic_policy(a,123,self.env())
    def test_no_shared_directory_fallback_without_session(self):
        with self.assertRaisesRegex(ValueError,'owned session'):automatic_policy(self.app(),123,{})
    def test_explicit_scope_and_directory_preserved(self):
        e=dict(self.env(),SOLIDWORKS_RECOVERY_ALL_DOCUMENTS='0',SOLIDWORKS_RECOVERY_DIRECTORY='C:/private')
        p=automatic_policy(self.app(),123,e)
        self.assertFalse(p['settings']['all_documents']);self.assertEqual(p['directory'],'C:/private')
    def test_live_native_interval_changes_do_not_allow_scope_changes(self):
        before={'interval_seconds':300,'assemblies':True}
        after={'interval_seconds':60,'assemblies':True}
        self.assertFalse(matching_settings(before,after))
        self.assertTrue(matching_settings(before,after,True))
        self.assertFalse(matching_settings(before,dict(after,assemblies=False),True))
        self.assertFalse(matching_settings(dict(before,interval_seconds=float('nan')),after,True))

if __name__=='__main__':unittest.main()
