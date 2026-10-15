"""No CAD: startup lifecycle regressions against production recovery modules."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from solidworks_mcp import recovery_monitor as monitor
from solidworks_mcp import recovery_service as service


class StartupFenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name); self.session = self.root / 'session.json'
        self.current = {'pid': 123, 'start_time': 'current-start'}
        self.session.write_text(json.dumps(self.current), encoding='utf-8')
        self.pending_path = self.root / 'worker-startup.json'
        self.pending = {'kind': 'recovery_worker_startup', 'protocol_version': 2,
                        'pid': 123, 'process_start_time': 'current-start',
                        'session_file': str(self.session.resolve()), 'startup_token': 'a' * 32}
        self.write_pending()
        self.env = {'SOLIDWORKS_RECOVERY_MONITOR': '1', 'SOLIDWORKS_SESSION_FILE': str(self.session),
                    'SOLIDWORKS_RECOVERY_DIRECTORY': str(self.root)}

    def write_pending(self):
        self.pending_path.write_text(json.dumps(self.pending), encoding='utf-8')

    def worker_scope(self, pid=123, identity='current-start', token=None):
        return monitor.worker_startup(self.session, self.root, pid, identity, token or 'a' * 32)

    def test_worker_claims_exact_target_before_backend(self):
        with patch.object(monitor, 'monitor_lock', return_value=nullcontext()), \
             patch.object(monitor, 'process_identity', return_value='current-start'), \
             patch.object(monitor, 'CadBackend') as backend:
            with self.worker_scope() as target:
                self.assertEqual(target, self.current)
                record = json.loads(self.pending_path.read_text())
                self.assertEqual(record['worker_pid'], os.getpid())
                self.assertTrue(record['worker_start_time'])
                self.assertTrue(record['worker_executable'])
            backend.assert_not_called()

    def test_delayed_worker_cannot_adopt_new_session_target(self):
        self.session.write_text(json.dumps({'pid': 456, 'start_time': 'new-start'}))
        before = self.pending_path.read_bytes()
        with patch.object(monitor, 'monitor_lock', return_value=nullcontext()), \
             patch.object(monitor, 'process_identity', return_value='new-start'), \
             patch.object(monitor, 'CadBackend') as backend:
            with self.assertRaisesRegex(RuntimeError, 'target|identity'):
                with self.worker_scope(): self.fail('delayed worker entered')
            backend.assert_not_called()
        self.assertEqual(self.pending_path.read_bytes(), before)

    def test_replaced_token_cannot_claim(self):
        with patch.object(monitor, 'monitor_lock', return_value=nullcontext()), \
             patch.object(monitor, 'process_identity', return_value='current-start'):
            with self.assertRaisesRegex(RuntimeError, 'token|reservation'):
                with self.worker_scope(token='b' * 32): self.fail('old token entered')

    def test_worker_unknown_or_reused_target_refuses(self):
        for outcome in (None, 'reused-start', PermissionError('denied')):
            with self.subTest(outcome=str(outcome)), \
                 patch.object(monitor, 'monitor_lock', return_value=nullcontext()), \
                 patch.object(monitor, 'process_identity', side_effect=(outcome if isinstance(outcome, Exception) else None), return_value=outcome):
                with self.assertRaises((RuntimeError, PermissionError)):
                    with self.worker_scope(): self.fail('unverified target entered')

    def test_startup_arguments_pin_expected_identity(self):
        self.pending_path.unlink()
        def launch(executable, cwd, arguments, **kwargs):
            self.assertEqual(arguments[arguments.index('--expected-pid') + 1], '123')
            self.assertEqual(arguments[arguments.index('--expected-start-time') + 1], 'current-start')
            raise RuntimeError('test launch stopped before process creation')
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(service, 'process_identity', return_value='current-start'), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'start_desktop_process', side_effect=launch):
            with self.assertRaisesRegex(RuntimeError, 'test launch stopped'):
                service.ensure_recovery_worker(123)

    def test_immediate_launch_failure_can_retry_without_creator_exit(self):
        self.pending_path.unlink()
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(service, 'process_identity', return_value='current-start'), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'start_desktop_process', side_effect=RuntimeError('before child')) as launch:
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, 'before child'):
                    service.ensure_recovery_worker(123)
            self.assertEqual(launch.call_count, 2)
        self.assertTrue(list((self.root / 'retired-startups').glob('*.json')))

    def stale(self, versioned=True):
        self.pending.update(pid=100, process_start_time='old-start')
        if versioned:
            self.pending.update(worker_pid=200, worker_start_time='old-worker-start',
                                worker_executable=str(Path(sys._base_executable).resolve()).casefold())
        else:
            self.pending.pop('protocol_version', None)
        self.write_pending()

    def test_known_dead_stale_claim_is_archived_then_retried(self):
        self.stale()
        original = self.pending_path.read_bytes()
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(service, 'process_identity', side_effect=lambda pid: 'current-start' if pid == 123 else None), \
             patch.object(service, 'worker_identity', return_value=None), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'start_desktop_process', side_effect=RuntimeError('test next launch')) as launch:
            with self.assertRaisesRegex(RuntimeError, 'test next launch'):
                service.ensure_recovery_worker(123)
            launch.assert_called_once()
        self.assertIn(original, [p.read_bytes() for p in (self.root / 'retired-startups').glob('*.json')])

    def test_legacy_unknown_has_actionable_diagnostic_and_preserves_bytes(self):
        self.stale(versioned=False); before = self.pending_path.read_bytes()
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(service, 'process_identity', return_value='current-start'), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'start_desktop_process') as launch:
            with self.assertRaisesRegex(RuntimeError, 'retire-stale-startup'):
                service.ensure_recovery_worker(123)
            launch.assert_not_called()
        self.assertEqual(before, self.pending_path.read_bytes())

    def retire(self, scan=None, identity=None):
        with patch.object(service, 'process_identity', side_effect=identity or (lambda pid: 'current-start' if pid == 123 else None)), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'observe_session_workers', return_value=[] if scan is None else scan), \
             patch.object(service, 'start_desktop_process') as launch:
            result = service.retire_stale_startup(self.session, self.root)
            launch.assert_not_called()
            return result

    def test_explicit_legacy_retirement_preserves_original_without_launch(self):
        self.stale(versioned=False); before = self.pending_path.read_bytes()
        result = self.retire()
        self.assertFalse(self.pending_path.exists())
        self.assertEqual(Path(result['reservation_archive']).read_bytes(), before)
        self.assertFalse(result['worker_launched'])

    def test_legacy_live_worker_scan_refuses(self):
        self.stale(versioned=False); before = self.pending_path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'worker|launcher'):
            self.retire(scan=[{'pid': 200, 'session_file': str(self.session)}])
        self.assertEqual(self.pending_path.read_bytes(), before)

    def test_legacy_target_reuse_and_unknown_refuse(self):
        self.stale(versioned=False)
        for outcome in ('new-identity', PermissionError('denied')):
            def identity(pid):
                if pid == 123: return 'current-start'
                if isinstance(outcome, Exception): raise outcome
                return outcome
            with self.subTest(outcome=str(outcome)), self.assertRaises((RuntimeError, PermissionError)):
                self.retire(identity=identity)
            self.assertTrue(self.pending_path.exists())

    def test_legacy_foreign_session_refuses(self):
        self.stale(versioned=False)
        self.pending['session_file'] = str(self.root / 'other-session.json'); self.write_pending()
        with self.assertRaisesRegex(RuntimeError, 'session'):
            self.retire()

    def test_stale_claim_live_reused_and_unknown_worker_all_preserved(self):
        self.stale(); before = self.pending_path.read_bytes()
        for outcome in (('python.exe', 'old-worker-start'), ('other.exe', 'reused'), PermissionError('denied')):
            with self.subTest(outcome=str(outcome)), \
                 patch.dict(os.environ, self.env, clear=True), \
                 patch.object(service, 'process_identity', side_effect=lambda pid: 'current-start' if pid == 123 else None), \
                 patch.object(service, 'worker_identity', side_effect=(outcome if isinstance(outcome, Exception) else None), return_value=outcome), \
                 patch.object(service, 'monitor_lock', return_value=nullcontext()), \
                 patch.object(service, 'start_desktop_process') as launch:
                with self.assertRaises((RuntimeError, PermissionError)):
                    service.ensure_recovery_worker(123)
                launch.assert_not_called()
            self.assertEqual(self.pending_path.read_bytes(), before)

    def test_legacy_scan_unknown_preserves_reservation(self):
        self.stale(versioned=False); before = self.pending_path.read_bytes()
        with patch.object(service, 'process_identity', side_effect=lambda pid: 'current-start' if pid == 123 else None), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'observe_session_workers', side_effect=PermissionError('worker command line denied')):
            with self.assertRaises(PermissionError): service.retire_stale_startup(self.session, self.root)
        self.assertEqual(self.pending_path.read_bytes(), before)

    def test_legacy_race_rechecks_reservation_and_session(self):
        for changed_file in ('pending', 'session', 'status'):
            with self.subTest(changed_file=changed_file):
                self.session.write_text(json.dumps(self.current))
                (self.root / 'monitor.json').unlink(missing_ok=True)
                self.stale(versioned=False)
                def scan(session):
                    if changed_file == 'pending':
                        self.pending['startup_token'] = 'b' * 32; self.write_pending()
                    elif changed_file == 'session':
                        self.session.write_text(json.dumps({'pid': 999, 'start_time': 'changed'}))
                    else:
                        (self.root / 'monitor.json').write_text('{}')
                    return []
                with patch.object(service, 'process_identity', side_effect=lambda pid: 'current-start' if pid == 123 else None), \
                     patch.object(service, 'monitor_lock', return_value=nullcontext()), \
                     patch.object(service, 'observe_session_workers', side_effect=scan):
                    with self.assertRaisesRegex(RuntimeError, 'changed|appeared'):
                        service.retire_stale_startup(self.session, self.root)
                self.assertTrue(self.pending_path.exists())

    def test_stop_marker_and_busy_monitor_refuse_retirement(self):
        self.stale(versioned=False); before = self.pending_path.read_bytes()
        (self.root / 'requested.stop').touch()
        with self.assertRaisesRegex(RuntimeError, 'stop marker'): self.retire()
        (self.root / 'requested.stop').unlink()
        def lock(name):
            if str(name).endswith('.worker-launch'): return nullcontext()
            raise RuntimeError('This session already has a recovery monitor')
        with patch.object(service, 'monitor_lock', side_effect=lock), \
             patch.object(service, 'observe_session_workers') as scan:
            with self.assertRaisesRegex(RuntimeError, 'already has'):
                service.retire_stale_startup(self.session, self.root)
            scan.assert_not_called()
        self.assertEqual(self.pending_path.read_bytes(), before)

    def test_worker_cannot_claim_same_attempt_twice(self):
        with patch.object(monitor, 'monitor_lock', return_value=nullcontext()), \
             patch.object(monitor, 'process_identity', return_value='current-start'):
            with self.worker_scope(): pass
            with self.assertRaisesRegex(RuntimeError, 'already claimed'):
                with self.worker_scope(): self.fail('duplicate claimed')

    def test_known_launcher_exited_before_claim_can_retry_same_target(self):
        self.pending.update(launcher_pid=200, launcher_start_time='launcher-start',
                            launcher_executable='python.exe', launch_state='created_suspended')
        self.write_pending(); original = self.pending_path.read_bytes()
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(service, 'process_identity', return_value='current-start'), \
             patch.object(service, 'worker_identity', return_value=None), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'observe_session_workers', return_value=[]) as scan, \
             patch.object(service, 'start_desktop_process', side_effect=RuntimeError('retry after import failure')) as launch:
            with self.assertRaisesRegex(RuntimeError, 'retry after import failure'):
                service.ensure_recovery_worker(123)
            launch.assert_called_once(); scan.assert_called_once_with(self.session)
        self.assertIn(original, [p.read_bytes() for p in (self.root / 'retired-startups').glob('*.json')])

    def test_unclaimed_attempt_live_launcher_or_worker_or_unknown_refuses_retry(self):
        self.pending.update(launcher_pid=200, launcher_start_time='launcher-start',
                            launcher_executable='python.exe', launch_state='created_suspended')
        self.write_pending(); original = self.pending_path.read_bytes()
        cases = [(('python.exe', 'launcher-start'), [], None),
                 (('other.exe', 'reused'), [], None),
                 (None, [{'pid': 300}], None),
                 (None, [], PermissionError('inventory denied'))]
        for live, workers, error in cases:
            with self.subTest(live=live, workers=workers, error=str(error)), \
                 patch.dict(os.environ, self.env, clear=True), \
                 patch.object(service, 'process_identity', return_value='current-start'), \
                 patch.object(service, 'worker_identity', return_value=live), \
                 patch.object(service, 'monitor_lock', return_value=nullcontext()), \
                 patch.object(service, 'observe_session_workers', return_value=workers, side_effect=error), \
                 patch.object(service, 'start_desktop_process') as launch:
                with self.assertRaises((RuntimeError, PermissionError)):
                    service.ensure_recovery_worker(123)
                launch.assert_not_called()
            self.assertEqual(self.pending_path.read_bytes(), original)

    def test_status_session_changed_after_initial_validation_is_rejected(self):
        self.stale(versioned=False)
        status = self.root / 'monitor.json'
        record = {'kind': 'part_recovery_monitor', 'session_file': str(self.session.resolve()),
                  'pid': 100, 'process_start_time': 'old-start', 'startup_token': self.pending['startup_token'],
                  'worker_pid': 200, 'worker_start_time': 'old-worker-start'}
        status.write_text(json.dumps(record))
        def identity(pid):
            if pid == 123:
                record['session_file'] = str(self.root / 'other-session.json')
                status.write_text(json.dumps(record))
                return 'current-start'
            return None
        with patch.object(service, 'process_identity', side_effect=identity), \
             patch.object(service, 'monitor_lock', return_value=nullcontext()), \
             patch.object(service, 'observe_session_workers') as scan:
            with self.assertRaisesRegex(RuntimeError, 'reserved attempt'):
                service.retire_stale_startup(self.session, self.root)
            scan.assert_not_called()
        self.assertTrue(self.pending_path.exists()); self.assertTrue(status.exists())

    def test_archive_link_outside_private_directory_is_rejected(self):
        self.stale(versioned=False); before = self.pending_path.read_bytes()
        archive = self.root / 'retired-startups'
        real_resolve = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == archive: return self.root.parent / 'another-session'
            return real_resolve(path, *args, **kwargs)
        with patch.object(Path, 'resolve', resolve):
            with self.assertRaisesRegex(RuntimeError, 'archive path'):
                self.retire()
        self.assertEqual(self.pending_path.read_bytes(), before)


if __name__ == '__main__': unittest.main()
