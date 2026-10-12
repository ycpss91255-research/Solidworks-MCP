import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from launch_solidworks import launch_session


class LauncherSessionTests(unittest.TestCase):
    def test_repeat_launch_reuses_only_this_sessions_pid(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)/'session.json'
            with patch('launch_solidworks._launch_locked', return_value=123) as start, \
                 patch('solidworks_mcp.automation.managed_session.process_identity', return_value='identity'):
                self.assertEqual(launch_session('SLDWORKS.exe', state), (123,True))
                self.assertEqual(launch_session('SLDWORKS.exe', state), (123,False))
                start.assert_called_once()

    def test_reused_pid_does_not_launch_or_attach(self):
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)/'session.json'
            state.write_text(json.dumps({'pid':123,'start_time':'old'}))
            with patch('launch_solidworks._launch_locked') as start, \
                 patch('solidworks_mcp.automation.managed_session.process_identity', return_value='new'):
                with self.assertRaisesRegex(RuntimeError, 'PID was reused'):
                    launch_session('SLDWORKS.exe', state)
                start.assert_not_called()
