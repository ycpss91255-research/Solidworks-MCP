import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from solidworks_mcp.diagnostics.resource_wait import resource_ready, wait_and_run, exclusive_monitor


class ResourceWaitTests(unittest.TestCase):
    def test_absolute_commit_reserve_cannot_be_overridden_by_percentage(self):
        gib=1024**3
        good={'commit_bytes':96*gib,'commit_limit_bytes':100*gib,'available_physical_bytes':6*gib}
        self.assertTrue(resource_ready(good,max_commit=99,min_commit_reserve_mb=4096))
        self.assertFalse(resource_ready(dict(good,commit_bytes=96*gib+1),max_commit=99,min_commit_reserve_mb=4096))

    def test_explicit_reserve_policy_does_not_change_default_percentage_gate(self):
        gib=1024**3
        value={'commit_bytes':int(45.5*gib),'commit_limit_bytes':50*gib,'available_physical_bytes':6*gib}
        self.assertFalse(resource_ready(value))
        self.assertTrue(resource_ready(value,max_commit=95,min_commit_reserve_mb=4096))

    def test_reserve_dips_reset_consecutive_samples_and_launch_only_once(self):
        gib=1024**3
        good={'commit_bytes':96*gib,'commit_limit_bytes':100*gib,'available_physical_bytes':6*gib}
        bad=dict(good,commit_bytes=97*gib)
        sample=Mock(side_effect=[good,good,bad,good,good,good]);run=Mock(return_value=0)
        self.assertEqual(wait_and_run(['private'],sample=sample,sleep=Mock(),run=run,
                                     max_commit=99,min_commit_reserve_mb=4096),0)
        self.assertEqual(sample.call_count,6);run.assert_called_once_with(['private'])
    def test_unknown_or_invalid_memory_never_opens_gate(self):
        for value in ({'error': 5}, {}, {'commit_bytes': 0, 'commit_limit_bytes': 0},
                      {'commit_bytes': 1, 'commit_limit_bytes': 100, 'available_physical_bytes': -1},
                      {'commit_bytes': 1, 'commit_limit_bytes': float('inf'), 'available_physical_bytes': 5*1024**3}):
            self.assertFalse(resource_ready(value))

    def test_waits_through_pressure_and_requires_consecutive_healthy_samples(self):
        good = {'commit_bytes': 80, 'commit_limit_bytes': 100, 'available_physical_bytes': 5 * 1024**3}
        bad = dict(good, commit_bytes=96)
        sample = Mock(side_effect=[bad, good, bad, good, good, good])
        run, sleep, record = Mock(return_value=0), Mock(), Mock()
        result = wait_and_run(['guarded', 'private-runner'], sample=sample,
                              sleep=sleep, record=record, run=run, cancelled=lambda: False)
        self.assertEqual(result, 0)
        run.assert_called_once_with(['guarded', 'private-runner'])
        self.assertEqual(sample.call_count, 6)
        self.assertEqual(record.call_args.args[0]['phase'], 'completed')

    def test_cancellation_during_wait_never_launches(self):
        run = Mock()
        self.assertEqual(wait_and_run(['guarded'], run=run, cancelled=lambda: True, record=Mock()), 2)
        run.assert_not_called()

    def test_failed_command_is_recorded_without_automatic_replay(self):
        good = {'commit_bytes': 80, 'commit_limit_bytes': 100, 'available_physical_bytes': 5 * 1024**3}
        run, record = Mock(return_value=17), Mock()
        self.assertEqual(wait_and_run(['guarded'], sample=lambda: good, sleep=Mock(),
                                     cancelled=lambda: False, record=record, run=run), 17)
        run.assert_called_once()
        self.assertEqual(record.call_args.args[0]['phase'], 'failed')

    def test_only_one_monitor_can_own_the_same_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'monitor.lock'
            with exclusive_monitor(path):
                with self.assertRaises(OSError):
                    with exclusive_monitor(path):
                        self.fail('duplicate monitor acquired the lock')
            with exclusive_monitor(path):
                pass
