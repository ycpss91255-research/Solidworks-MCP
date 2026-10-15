"""No CAD. Unit controls preserve unknown/racy inventory as a refusal."""
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from solidworks_mcp import recovery_process_scan as scan


class RecoveryProcessScanTests(unittest.TestCase):
    def setUp(self):
        self.session = str(Path('test-session-scan.json').resolve())
        self.image = str(Path(sys._base_executable).resolve())
        self.row = dict(pid=123, name='python.exe', image=self.image,
                        creation_date='20261015120000.123456+000',
                        command_line=subprocess.list2cmdline([self.image, '-m',
                            'solidworks_mcp.recovery_monitor', '--session-file', self.session]))
        self.identity = dict(pid=123, image=self.image, process_start_time='start',
                             creation_microseconds=scan._creation_microseconds(self.row['creation_date']),
                             is_live=lambda: True)

    def observe(self, first, second=None, identity=None, error=None):
        @contextmanager
        def hold(pid):
            if error:
                raise error
            yield identity or self.identity
        with patch.object(scan, '_process_snapshot', side_effect=[first, first if second is None else second]), \
             patch.object(scan, '_hold_identity', side_effect=hold):
            return scan.observe_session_workers(self.session)

    def test_stable_empty_inventory(self):
        self.assertEqual(self.observe([]), [])

    def test_exact_worker_includes_identity(self):
        result = self.observe([self.row])
        self.assertEqual(result[0]['pid'], 123)
        self.assertEqual(result[0]['process_start_time'], 'start')

    def test_other_session_is_not_this_worker(self):
        row = dict(self.row, command_line=self.row['command_line'].replace('test-session-scan', 'other-session'))
        self.assertEqual(self.observe([row]), [])

    def test_same_session_path_case_and_equals_argument(self):
        row = dict(self.row, command_line=subprocess.list2cmdline([self.image, '-m',
                   'solidworks_mcp.recovery_monitor', '--session-file=' + self.session.upper()]))
        self.assertEqual(len(self.observe([row])), 1)

    def test_regular_python_is_not_a_worker(self):
        row = dict(self.row, command_line=subprocess.list2cmdline([self.image, 'unrelated.py']))
        self.assertEqual(self.observe([row]), [])

    def test_both_launcher_and_actual_worker_are_retained(self):
        row2 = dict(self.row, pid=124)
        @contextmanager
        def hold(pid):
            yield dict(self.identity, pid=pid)
        with patch.object(scan, '_process_snapshot', return_value=[self.row, row2]), \
             patch.object(scan, '_hold_identity', side_effect=hold):
            self.assertEqual({row['pid'] for row in scan.observe_session_workers(self.session)}, {123, 124})

    def test_process_born_between_snapshots_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'changed'):
            self.observe([], [self.row])

    def test_candidate_vanishing_before_open_is_unknown(self):
        with self.assertRaises(scan.RecoveryInventoryUncertain):
            self.observe([self.row], error=OSError('PID vanished'))

    def test_candidate_vanishing_after_second_snapshot_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'exited'):
            self.observe([self.row], identity=dict(self.identity, is_live=lambda: False))

    def test_access_denied_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'incomplete'):
            self.observe([self.row], error=PermissionError('access denied'))

    def test_unreadable_python_command_line_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'unreadable'):
            self.observe([dict(self.row, command_line=None)])

    def test_reused_pid_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'identity changed'):
            self.observe([self.row], identity=dict(self.identity,
                         creation_microseconds=self.identity['creation_microseconds'] + 1))

    def test_image_mismatch_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'identity changed'):
            self.observe([self.row], identity=dict(self.identity, image='C:/other/python.exe'))

    def test_ambiguous_worker_session_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'ambiguous'):
            self.observe([dict(self.row, command_line=self.row['command_line'] + ' --session-file C:/other.json')])

    def test_relative_worker_session_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'absolute'):
            self.observe([dict(self.row, command_line=subprocess.list2cmdline([self.image, '-m',
                         'solidworks_mcp.recovery_monitor', '--session-file', 'relative.json']))])

    def test_nonstandard_recovery_invocation_is_unknown(self):
        with self.assertRaisesRegex(scan.RecoveryInventoryUncertain, 'Ambiguous'):
            self.observe([dict(self.row, command_line=self.image + ' -c "import solidworks_mcp.recovery_monitor"')])

    def test_incomplete_creation_time_is_unknown(self):
        with self.assertRaises(scan.RecoveryInventoryUncertain):
            self.observe([dict(self.row, creation_date='20261015******.******+000')])


if __name__ == '__main__':
    unittest.main()
