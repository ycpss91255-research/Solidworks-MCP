import unittest
from unittest.mock import patch
from pathlib import Path
from launch_solidworks import launch


class LauncherTests(unittest.TestCase):
    def test_refuses_third_instance(self):
        with patch('launch_solidworks.running_pids', return_value=[1,2]), \
             patch('launch_solidworks.subprocess.Popen') as start:
            with self.assertRaisesRegex(RuntimeError, 'Two or more'):
                launch('SLDWORKS.exe')
            start.assert_not_called()

    def test_full_path_installation_cwd_and_hidden_start(self):
        executable = Path('C:/fake/SOLIDWORKS/SLDWORKS.exe')
        with patch('launch_solidworks.running_pids', return_value=[1]), \
             patch.object(Path, 'resolve', return_value=executable), \
             patch('launch_solidworks.subprocess.Popen') as start:
            start.return_value.pid = 2
            self.assertEqual(launch(executable), 2)
            self.assertEqual(start.call_args.args[0], [str(executable)])
            self.assertEqual(start.call_args.kwargs['cwd'], str(executable.parent))
            self.assertEqual(start.call_args.kwargs['startupinfo'].wShowWindow, 0)

if __name__ == '__main__':
    unittest.main()
