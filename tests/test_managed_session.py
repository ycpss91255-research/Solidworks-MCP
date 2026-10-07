from contextlib import nullcontext
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from solidworks_mcp.automation.managed_session import connect_managed


class ManagedSessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)/'session.json'
        self.automation = MagicMock()
        self.automation._configured_target = '123'
        self.automation._connect_target.side_effect = lambda: {'success':True,'data':{'pid':456}}
        for patcher in (
            patch.dict(os.environ, {'SOLIDWORKS_SESSION_FILE':str(self.path)}),
            patch('launch_solidworks.launcher_lock', side_effect=nullcontext),
            patch('solidworks_mcp.utils.find_solidworks', return_value='SLDWORKS.exe'),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_exited_target_launches_once_and_other_connections_reuse_manifest(self):
        with patch('solidworks_mcp.automation.managed_session.process_identity',
                   side_effect=lambda pid: None if pid==123 else 'created'), \
             patch('launch_solidworks._launch_locked', return_value=456) as launch:
            first = connect_managed(self.automation)
            second = connect_managed(self.automation)
            self.assertTrue(first['data']['launched'])
            self.assertFalse(second['data']['launched'])
            self.assertEqual(self.automation._target_pid, '456')
            self.assertEqual(json.loads(self.path.read_text())['pid'], 456)
            launch.assert_called_once()

    def test_running_target_with_com_failure_never_launches(self):
        self.automation._connect_target.side_effect = lambda: {'success':False,'message':'COM unavailable'}
        with patch('solidworks_mcp.automation.managed_session.process_identity', return_value='created'), \
             patch('launch_solidworks._launch_locked') as launch:
            result = connect_managed(self.automation)
            self.assertFalse(result['success'])
            launch.assert_not_called()

    def test_reused_pid_is_rejected(self):
        self.path.write_text(json.dumps({'pid':456,'start_time':'old',
                                       'configured_pid':'123','ready':True}))
        with patch('solidworks_mcp.automation.managed_session.process_identity', return_value='new'), \
             patch('launch_solidworks._launch_locked') as launch:
            with self.assertRaisesRegex(RuntimeError, 'reused'):
                connect_managed(self.automation)
            launch.assert_not_called()

    def test_access_denied_does_not_launch(self):
        with patch('solidworks_mcp.automation.managed_session.process_identity', side_effect=PermissionError), \
             patch('launch_solidworks._launch_locked') as launch:
            with self.assertRaises(PermissionError):
                connect_managed(self.automation)
            launch.assert_not_called()

    def test_requires_absolute_session_path(self):
        with patch.dict(os.environ, {'SOLIDWORKS_SESSION_FILE':'relative.json'}), \
             patch('launch_solidworks._launch_locked') as launch:
            with self.assertRaises(ValueError):
                connect_managed(self.automation)
            launch.assert_not_called()

if __name__ == '__main__':
    unittest.main()
