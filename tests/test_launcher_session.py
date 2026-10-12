import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from launch_solidworks import launch_session


class LauncherSessionTests(unittest.TestCase):
    def test_preload_without_routing_never_launches(self):
        with tempfile.TemporaryDirectory() as folder, patch('launch_solidworks._launch_locked') as start:
            with self.assertRaisesRegex(ValueError,'explicit routing paths'):
                launch_session('SLDWORKS.exe',Path(folder)/'state.json',journal_preload=True)
            start.assert_not_called()

    def test_private_recovery_cannot_be_inside_shared_journal_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            dll=root/'test.dll';dll.write_bytes(b'fixture')
            source=root/'shared';source.mkdir()
            with patch('launch_solidworks._launch_locked') as start:
                with self.assertRaisesRegex(ValueError,'outside the shared journal folder'):
                    launch_session('SLDWORKS.exe',root/'state.json',
                        journal_redirect=(dll,source,root/'private',source/'recovery'))
                start.assert_not_called()
            self.assertFalse((source/'recovery').exists())

    def test_stale_session_cannot_reuse_a_nonempty_private_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            state=root/'session.json'
            state.write_text(json.dumps({'pid':123,'start_time':'old'}))
            dll=root/'test.dll';dll.write_bytes(b'fixture')
            source=root/'source';source.mkdir()
            destination=root/'private';destination.mkdir()
            (destination/'swxJRNL.swj').write_text('preserved')
            with patch('launch_solidworks._launch_locked') as start, \
                 patch('solidworks_mcp.automation.managed_session.process_identity', return_value=None):
                with self.assertRaisesRegex(ValueError,'empty private directory'):
                    launch_session('SLDWORKS.exe',state,journal_redirect=(dll,source,destination))
                start.assert_not_called()
            self.assertEqual((destination/'swxJRNL.swj').read_text(),'preserved')

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
