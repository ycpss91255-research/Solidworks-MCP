"""Wait for lab headroom, then execute one explicit command once; no CAD API."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import time

from solidworks_mcp.script_trace import memory_snapshot


def same_live_process(handle, expected_start, *, wait=None, created=None):
    """A queryable kernel object and matching creation time do not prove life."""
    if wait is None:
        import win32event
        wait = win32event.WaitForSingleObject
    status = wait(handle, 0)
    if status == 0:  # Signaled process handle: exited, even if still queryable.
        return False
    if status != 258:  # WAIT_TIMEOUT: process is still running.
        raise RuntimeError(f'Unable to establish process liveness: wait={status}')
    if created is None:
        import win32process
        created = lambda value: win32process.GetProcessTimes(value)['CreationTime'].timestamp()
    return abs(created(handle) - expected_start) < .01


def resource_ready(snapshot, max_commit=90, min_available_mb=4096):
    try:
        commit = snapshot['commit_bytes']
        limit = snapshot['commit_limit_bytes']
        available = snapshot['available_physical_bytes']
        return (limit > 0 and commit >= 0 and available >= 0
                and 100 * commit / limit <= max_commit
                and available >= min_available_mb * 1024**2)
    except (KeyError, TypeError, ZeroDivisionError):
        return False


@contextmanager
def exclusive_monitor(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def wait_and_run(command, *, sample=memory_snapshot, sleep=time.sleep,
                 record=lambda value: None, run=None, cancelled=lambda: False,
                 interval=5, safe_samples=3, max_commit=90, min_available_mb=4096):
    if not command or safe_samples < 1 or not 1 <= interval <= 60:
        raise ValueError('Provide a command and valid sampling settings')
    if run is None:
        run = lambda cmd: subprocess.run(cmd, shell=False, creationflags=subprocess.CREATE_NO_WINDOW).returncode
    healthy = 0
    while True:
        if cancelled():
            record({'phase': 'cancelled'})
            return 2
        try:
            snapshot = sample()
        except Exception as error:
            snapshot = {'error': repr(error)}
        healthy = healthy + 1 if resource_ready(snapshot, max_commit, min_available_mb) else 0
        record({'phase': 'waiting', 'memory': snapshot, 'healthy_samples': healthy})
        if healthy >= safe_samples:
            if cancelled():
                record({'phase': 'cancelled'})
                return 2
            record({'phase': 'running', 'command': command})
            try:
                code = run(command)
            except Exception as error:
                record({'phase': 'failed', 'error': repr(error)})
                raise
            record({'phase': 'completed' if code == 0 else 'failed', 'return_code': code})
            return code
        sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-file', type=Path, required=True)
    parser.add_argument('--cancel-file', type=Path, required=True)
    parser.add_argument('--interval', type=int, default=5)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.state_file.is_absolute() or not args.cancel_file.is_absolute():
        parser.error('State and cancellation files must be absolute and chat-owned')
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    with exclusive_monitor(args.state_file.with_suffix('.lock')):
        if args.state_file.exists():
            previous = json.loads(args.state_file.read_text(encoding='utf-8'))
            if previous.get('phase') != 'waiting':
                raise RuntimeError('Command already started or monitor is terminal; inspect it before any replay')
        import win32api, win32process
        identity = {'worker_pid': os.getpid(),
                    'worker_start_time': win32process.GetProcessTimes(win32api.GetCurrentProcess())['CreationTime'].isoformat(),
                    'command': command}
        def record(value):
            value = dict(identity, **value, checked_at=datetime.now(timezone.utc).isoformat())
            with args.state_file.with_suffix('.events.jsonl').open('a', encoding='utf-8') as history:
                history.write(json.dumps(value) + '\n')
            temporary = args.state_file.with_suffix('.tmp')
            temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
            temporary.replace(args.state_file)
        return wait_and_run(command, record=record, interval=args.interval,
                            cancelled=args.cancel_file.exists)


if __name__ == '__main__':
    raise SystemExit(main())
