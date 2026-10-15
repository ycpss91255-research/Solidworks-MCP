"""Real Windows locks/files/owned Python children; no CAD backend is created."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from solidworks_mcp import recovery_monitor as monitor
from solidworks_mcp import recovery_service as service
from solidworks_mcp import recovery_process_scan as process_scan
from solidworks_mcp.automation.managed_session import write_state


def child_main(request_path):
    request = json.loads(Path(request_path).read_text())
    gate, release, result = (Path(request[key]) for key in ('gate', 'release', 'result'))
    deadline = time.monotonic() + 20
    while not gate.exists() and time.monotonic() < deadline:
        time.sleep(.01)
    if not gate.exists():
        raise RuntimeError('owned fixture gate timed out')
    if request.get('mode') == 'token_only_main':
        calls = []
        class BackendSpy:
            def __init__(self, pid, directory):
                calls.append(['construct', pid, str(directory)])
            def connect(self):
                calls.append(['connect'])
                return {'success': True}
            def probe(self):
                calls.append(['probe'])
                return {'state': 'clean'}
            def close(self):
                calls.append(['close'])
        argv = ['recovery_monitor', '--session-file', request['session'],
                '--directory', request['directory'], '--status-file',
                str(Path(request['directory'])/'monitor.json'), '--interval', '.01',
                '--max-ticks', '1', '--startup-token', request['token']]
        actual_run = monitor.run_monitor
        def no_ui_run(*args, **kwargs):
            return actual_run(*args, **dict(kwargs, dialog_reader=lambda pid: False))
        try:
            with patch.object(sys, 'argv', argv), \
                 patch.object(monitor, 'process_identity', return_value=request.get('observed_identity', 'fixture-target-start')), \
                 patch.object(monitor, 'CadBackend', BackendSpy), \
                 patch.object(monitor, 'run_monitor', side_effect=no_ui_run):
                monitor.main()
            outcome = {'accepted': True, 'backend_spy_calls': calls, 'cad_calls': 0}
        except Exception as error:
            outcome = {'accepted': False, 'error': str(error), 'backend_spy_calls': calls, 'cad_calls': 0}
        result.write_text(json.dumps(outcome))
        return
    try:
        # Only the CAD-specific identity check is a fake. Mutexes, pending file,
        # claiming process PID/start/image and lifecycle are real Windows state.
        with patch.object(monitor, 'process_identity', return_value='fixture-target-start'):
            with monitor.worker_startup(request['session'], request['directory'], 123,
                                        'fixture-target-start', request['token']):
                result.write_text(json.dumps({'claimed': True, 'cad_calls': 0}))
                while not release.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                if not release.exists():
                    raise RuntimeError('owned fixture release timed out')
    except Exception as error:
        if result.exists():
            raise
        result.write_text(json.dumps({'claimed': False, 'error': str(error), 'cad_calls': 0}))


class RecoveryStartupWindowsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='swmcp-fence-native-')
        self.directory = Path(self.temporary.name)
        self.session = self.directory / 'session.json'
        self.pending = self.directory / 'worker-startup.json'
        self.target = {'pid': 123, 'start_time': 'fixture-target-start'}
        write_state(self.session, self.target)
        self.reserve('first-token')
        self.children = []

    def tearDown(self):
        for child, request in self.children:
            Path(request['gate']).touch()
            Path(request['release']).touch()
        for child, request in self.children:
            try:
                output, error = child.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                child.terminate()  # only this test's fresh Popen handle
                child.communicate(timeout=5)
                raise
            self.assertEqual(child.returncode, 0, error.decode(errors='replace'))
        self.temporary.cleanup()

    def reserve(self, token):
        write_state(self.pending, {'kind': 'recovery_worker_startup', 'protocol_version': 2,
            'pid': 123, 'process_start_time': 'fixture-target-start',
            'session_file': str(self.session.resolve()), 'startup_token': token,
            'launch_state': 'reserved'})

    def spawn(self, name, token='first-token', released=True, **options):
        request = {'directory': str(self.directory), 'session': str(self.session),
                   'token': token, 'gate': str(self.directory / (name + '.gate')),
                   'release': str(self.directory / (name + '.release')),
                   'result': str(self.directory / (name + '.result.json'))}
        request.update(options)
        request_path = self.directory / (name + '.request.json')
        request_path.write_text(json.dumps(request))
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--child', str(request_path)],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x08000000)
        self.children.append((child, request))
        if released:
            Path(request['gate']).touch()
        return child, request

    def outcome(self, child, request):
        path = Path(request['result'])
        deadline = time.monotonic() + 10
        while not path.exists() and time.monotonic() < deadline and child.poll() is None:
            time.sleep(.01)
        self.assertTrue(path.exists(), 'child produced no guarded outcome')
        return json.loads(path.read_text())

    def test_parent_launch_mutex_does_not_block_worker_claim(self):
        with monitor.monitor_lock(str(self.session) + '.worker-launch'):
            child, request = self.spawn('launch-lock')
            self.assertTrue(self.outcome(child, request)['claimed'])

    def test_active_monitor_mutex_refuses_duplicate_without_file_write(self):
        before = self.pending.read_bytes()
        with monitor.monitor_lock(self.session):
            child, request = self.spawn('monitor-lock')
            self.assertFalse(self.outcome(child, request)['claimed'])
        self.assertEqual(self.pending.read_bytes(), before)

    def test_two_concurrent_claimants_have_exactly_one_winner(self):
        first = self.spawn('first', released=False)
        second = self.spawn('second', released=False)
        Path(first[1]['gate']).touch()
        Path(second[1]['gate']).touch()
        outcomes = [self.outcome(*item) for item in (first, second)]
        self.assertEqual(sum(item['claimed'] for item in outcomes), 1)
        pending = json.loads(self.pending.read_text())
        self.assertGreater(pending['worker_pid'], 0)
        self.assertTrue(pending['worker_start_time'])

    def test_delayed_old_token_has_no_claim_or_status_side_effect(self):
        child, request = self.spawn('late', released=False)
        with monitor.monitor_lock(self.session):
            self.reserve('replacement-token')
        before = self.pending.read_bytes()
        Path(request['gate']).touch()
        outcome = self.outcome(child, request)
        self.assertFalse(outcome['claimed'])
        self.assertIn('token', outcome['error'])
        self.assertEqual(self.pending.read_bytes(), before)
        self.assertFalse((self.directory / 'monitor.json').exists())

    def test_claimed_child_natural_exit_can_retire_and_new_attempt_claims(self):
        child, request = self.spawn('exiting')
        self.assertTrue(self.outcome(child, request)['claimed'])
        original = self.pending.read_bytes()
        Path(request['release']).touch()
        child.communicate(timeout=10)
        self.assertEqual(child.returncode, 0)
        with monitor.monitor_lock(str(self.session) + '.worker-launch'), \
             patch.object(service, 'process_identity', return_value='fixture-target-start'):
            archive = service._retire_terminal_pending(self.session, self.directory, self.target)
        self.assertEqual(archive.read_bytes(), original)
        self.assertFalse(self.pending.exists())
        self.reserve('retry-token')
        next_child, next_request = self.spawn('retry', token='retry-token')
        self.assertTrue(self.outcome(next_child, next_request)['claimed'])

    def test_real_preclaim_launcher_exit_and_empty_inventory_allow_same_target_retry(self):
        import win32process
        child = subprocess.Popen([sys.executable, '-c', 'import sys;sys.exit(0)'],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=0x08000000)
        try:
            start = win32process.GetProcessTimes(child._handle)['CreationTime'].isoformat()
            child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0)
            pending = json.loads(self.pending.read_text())
            pending.update(launcher_pid=child.pid, launcher_start_time=start,
                           launcher_executable=str(Path(sys.executable).resolve()),
                           launch_state='created_suspended')
            write_state(self.pending, pending)
            original = self.pending.read_bytes()
            with monitor.monitor_lock(str(self.session) + '.worker-launch'), \
                 patch.object(service, 'process_identity', return_value='fixture-target-start'):
                # No inventory, OS worker identity, file, or mutex mocks here.
                archive = self.retire_with_stable_inventory(original)
            self.assertEqual(archive.read_bytes(), original)
            self.assertFalse(self.pending.exists())
            self.reserve('preclaim-retry-token')
            next_child, next_request = self.spawn('preclaim-retry', token='preclaim-retry-token')
            self.assertTrue(self.outcome(next_child, next_request)['claimed'])
        finally:
            if child.poll() is None:
                child.terminate()
                child.communicate(timeout=5)

    def retire_with_stable_inventory(self, original):
        # The real whole-machine inventory can change between its snapshots.
        # Retry only its conservative refusal, after proving no side effects.
        children_before = list(self.children)
        with patch.object(service, 'start_desktop_process', side_effect=AssertionError('retirement launched a worker')) as launch, \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('retirement spawned a process')) as spawn:
            for attempt in range(3):
                try:
                    archive = service._retire_terminal_pending(self.session, self.directory, self.target)
                except process_scan.RecoveryInventoryUncertain:
                    self.assertEqual(self.pending.read_bytes(), original)
                    self.assertFalse((self.directory / 'retired-startups').exists())
                    self.assertFalse((self.directory / 'monitor.json').exists())
                    self.assertEqual(self.children, children_before)
                    launch.assert_not_called()
                    spawn.assert_not_called()
                    if attempt == 2:
                        raise  # Exhaustion remains a failure, never a skip/pass.
                else:
                    launch.assert_not_called()
                    spawn.assert_not_called()
                    return archive

    def test_unstable_inventory_exhaustion_preserves_refusal_evidence(self):
        pending = json.loads(self.pending.read_text())
        pending.update(launcher_pid=456, launcher_start_time='exited-fixture-start',
                       launcher_executable=str(Path(sys.executable).resolve()))
        write_state(self.pending, pending)
        original = self.pending.read_bytes()
        # Real scanner decision, deterministic process-list churn; no live CAD
        # identity or OS process is needed to reproduce the uncertain inventory.
        appeared = {'pid': 98765, 'name': 'python.exe', 'image': str(Path(sys.executable).resolve()),
                    'command_line': 'python.exe unrelated.py', 'creation_date': 'fixture-time'}
        with monitor.monitor_lock(str(self.session) + '.worker-launch'), \
             patch.object(service, 'process_identity', return_value='fixture-target-start'), \
             patch.object(service, 'worker_identity', return_value=None), \
             patch.object(process_scan, '_process_snapshot', side_effect=[[], [appeared]] * 3) as snapshots:
            with self.assertRaisesRegex(process_scan.RecoveryInventoryUncertain, 'inventory changed'):
                self.retire_with_stable_inventory(original)
        self.assertEqual(snapshots.call_count, 6)
        self.assertEqual(self.pending.read_bytes(), original)
        self.assertFalse((self.directory / 'retired-startups').exists())
        self.assertFalse((self.directory / 'monitor.json').exists())
        self.assertEqual(self.children, [])

    def test_inventory_retry_does_not_swallow_unrelated_error(self):
        pending = json.loads(self.pending.read_text())
        pending.update(launcher_pid=456, launcher_start_time='exited-fixture-start',
                       launcher_executable=str(Path(sys.executable).resolve()))
        write_state(self.pending, pending)
        original = self.pending.read_bytes()
        with monitor.monitor_lock(str(self.session) + '.worker-launch'), \
             patch.object(service, 'process_identity', return_value='fixture-target-start'), \
             patch.object(service, 'worker_identity', return_value=None), \
             patch.object(service, 'observe_session_workers', side_effect=RuntimeError('unrelated refusal')) as scan:
            with self.assertRaisesRegex(RuntimeError, 'unrelated refusal'):
                self.retire_with_stable_inventory(original)
        self.assertEqual(scan.call_count, 1)
        self.assertEqual(self.pending.read_bytes(), original)
        self.assertFalse((self.directory / 'retired-startups').exists())
        self.assertFalse((self.directory / 'monitor.json').exists())
        self.assertEqual(self.children, [])

    def test_old_cli_token_only_main_is_fenced_before_backend(self):
        for arm in ('valid', 'wrong-token', 'wrong-target', 'wrong-session', 'wrong-os-start'):
            with self.subTest(arm=arm):
                write_state(self.session, self.target)
                self.reserve('first-token')
                pending = json.loads(self.pending.read_text())
                pending.pop('protocol_version')
                if arm == 'wrong-target':
                    write_state(self.session, {'pid': 124, 'start_time': 'other-target'})
                if arm == 'wrong-session':
                    pending['session_file'] = str(self.directory/'another-session.json')
                write_state(self.pending, pending)
                (self.directory/'monitor.json').unlink(missing_ok=True)
                before = self.pending.read_bytes()
                with monitor.monitor_lock(str(self.session) + '.worker-launch'):
                    child, request = self.spawn(arm, mode='token_only_main',
                        token='wrong-token' if arm == 'wrong-token' else 'first-token',
                        observed_identity='reused-start' if arm == 'wrong-os-start' else 'fixture-target-start')
                    outcome = self.outcome(child, request)
                child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0)
                if arm == 'valid':
                    self.assertTrue(outcome['accepted'])
                    self.assertEqual([item[0] for item in outcome['backend_spy_calls']],
                                     ['construct', 'connect', 'probe', 'close'])
                    self.assertEqual(outcome['backend_spy_calls'][0][1], 123)
                    claimed = json.loads(self.pending.read_text())
                    self.assertEqual(claimed['protocol_version'], 2)
                    self.assertEqual((claimed['pid'], claimed['process_start_time']),
                                     (123, 'fixture-target-start'))
                else:
                    self.assertFalse(outcome['accepted'])
                    self.assertEqual(outcome['backend_spy_calls'], [])
                    self.assertEqual(self.pending.read_bytes(), before)
                    self.assertFalse((self.directory/'monitor.json').exists())


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--child':
        child_main(sys.argv[2])
    else:
        unittest.main()
