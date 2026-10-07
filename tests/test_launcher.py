import unittest
from unittest.mock import patch
from pathlib import Path
from launch_solidworks import launch, check_journal_available
import tempfile
import win32api


class LauncherTests(unittest.TestCase):
    def test_refuses_third_instance(self):
        with patch('launch_solidworks.running_pids', return_value=[1,2]), \
             patch('launch_solidworks.start_desktop_process') as start:
            with self.assertRaisesRegex(RuntimeError, 'Two or more'):
                launch('SLDWORKS.exe')
            start.assert_not_called()

    def test_full_path_installation_cwd_and_hidden_start(self):
        executable = Path('C:/fake/SOLIDWORKS/SLDWORKS.exe')
        with patch('launch_solidworks.running_pids', return_value=[1]), \
             patch('launch_solidworks.check_journal_available'), \
             patch.object(Path, 'resolve', return_value=executable), \
             patch('launch_solidworks.start_desktop_process') as start:
            start.return_value = 2
            self.assertEqual(launch(executable), 2)
            self.assertEqual(start.call_args.args, (executable, executable.parent))

    def test_other_journal_errors_do_not_launch(self):
        with patch('launch_solidworks.running_pids', return_value=[1]), \
             patch.object(Path, 'resolve', return_value=Path('C:/fake/SLDWORKS.exe')), \
             patch('launch_solidworks.check_journal_available', side_effect=RuntimeError('Journal file unavailable')), \
             patch('launch_solidworks.start_desktop_process') as start:
            with self.assertRaisesRegex(RuntimeError, 'Journal file unavailable'):
                launch('SLDWORKS.exe')
            start.assert_not_called()

    def test_busy_journal_allows_independent_launch(self):
        with patch('launch_solidworks.running_pids', return_value=[1]), \
             patch.object(Path, 'resolve', return_value=Path('C:/fake/SLDWORKS.exe')), \
             patch('launch_solidworks.check_journal_available', return_value=['Journal in use']), \
             patch('launch_solidworks.start_desktop_process', return_value=2) as start:
            self.assertEqual(launch('SLDWORKS.exe'), 2)
            start.assert_called_once()

    def test_sharing_violation_is_notice_but_access_denied_is_error(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = Path(folder)/'SOLIDWORKS/SOLIDWORKS 2023/swxJRNL.swj'
            journal.parent.mkdir(parents=True)
            journal.write_text('test')
            with patch.dict('os.environ', {'APPDATA':folder}), \
                 patch('winreg.OpenKey', side_effect=FileNotFoundError), \
                 patch('launch_solidworks.win32file.CreateFile', side_effect=win32api.error(32,'CreateFile','busy')):
                self.assertEqual(len(check_journal_available()), 1)
            with patch.dict('os.environ', {'APPDATA':folder}), \
                 patch('winreg.OpenKey', side_effect=FileNotFoundError), \
                 patch('launch_solidworks.win32file.CreateFile', side_effect=win32api.error(5,'CreateFile','denied')):
                with self.assertRaisesRegex(RuntimeError, 'Windows error 5'):
                    check_journal_available()

if __name__ == '__main__':
    unittest.main()
