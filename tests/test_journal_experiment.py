import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from launch_solidworks import launch_journal_experiment


class JournalExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / 'journal'
        self.evidence = Path(self.temp.name) / 'lease.json'
        self.executable = Path('C:/fake/SLDWORKS.exe')

    def tearDown(self):
        self.temp.cleanup()

    def test_third_instance_does_not_change_registry(self):
        with patch.object(Path, 'resolve', return_value=self.executable), \
             patch('launch_solidworks.win32api.GetFileVersionInfo', return_value={'FileVersionMS':31 << 16}), \
             patch('launch_solidworks.running_pids', return_value=[1,2]), \
             patch('solidworks_mcp.journal_registry.JournalFolderLease') as lease, \
             patch('launch_solidworks._launch_locked') as start:
            with self.assertRaisesRegex(RuntimeError, 'No journal setting changed'):
                launch_journal_experiment(self.executable, self.folder, self.evidence)
            lease.assert_not_called()
            start.assert_not_called()

    def test_journal_must_belong_to_new_pid_and_existing_handle_must_remain(self):
        prior = {'pid':1, 'path':'C:/original/swxJRNL.swj'}
        own = {'pid':2, 'path':str(self.folder / 'swxJRNL.swj')}
        with patch('launch_solidworks.win32api.GetFileVersionInfo', return_value={'FileVersionMS':31 << 16}), \
             patch('launch_solidworks.running_pids', side_effect=[[1],[1,2]]), \
             patch('solidworks_mcp.process_files.journal_handles', side_effect=[[prior],[prior,own]]), \
             patch('solidworks_mcp.journal_registry.JournalFolderLease') as lease, \
             patch('launch_solidworks._launch_locked', return_value=2), \
             patch.object(Path, 'resolve', autospec=True, side_effect=lambda path, **kwargs: path):
            lease.return_value.__enter__.return_value.state = {}
            pid = launch_journal_experiment(self.executable, self.folder, self.evidence)
            self.assertEqual(pid, 2)
            state = lease.return_value.__enter__.return_value.state
            self.assertEqual(state['verified_journal_handles'], [prior,own])
            self.assertEqual(state['launched_pid'], 2)
            lease.return_value.__exit__.assert_called_once()

    def test_nonempty_folder_is_refused(self):
        self.folder.mkdir()
        (self.folder/'existing.swj').write_text('preserve')
        with patch('solidworks_mcp.journal_registry.JournalFolderLease') as lease:
            with self.assertRaisesRegex(ValueError, 'new, empty'):
                launch_journal_experiment(self.executable, self.folder, self.evidence)
            lease.assert_not_called()

    def test_another_pid_holding_requested_journal_is_not_proof(self):
        wrong_owner = {'pid':1, 'path':str(self.folder / 'swxJRNL.swj')}
        with patch('launch_solidworks.win32api.GetFileVersionInfo', return_value={'FileVersionMS':31 << 16}), \
             patch('launch_solidworks.running_pids', side_effect=[[1],[1,2]]), \
             patch('solidworks_mcp.process_files.journal_handles', side_effect=[[],[wrong_owner]]), \
             patch('solidworks_mcp.journal_registry.JournalFolderLease') as lease, \
             patch('launch_solidworks._launch_locked', return_value=2), \
             patch.object(Path, 'resolve', autospec=True, side_effect=lambda path, **kwargs: path), \
             patch('launch_solidworks.time.monotonic', side_effect=[0,46]):
            lease.return_value.__enter__.return_value.state = {}
            with self.assertRaisesRegex(RuntimeError, 'did not open its assigned journal'):
                launch_journal_experiment(self.executable, self.folder, self.evidence)
            lease.return_value.__exit__.assert_called_once()
