"""Freeze source/test digests and run the complete unittest discovery once."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    paths = set(ROOT.glob('*.py')) | set((ROOT/'solidworks_mcp').rglob('*.py'))
    paths |= set((ROOT/'tests').glob('test_*.py'))
    paths |= set((ROOT/'tests').glob('__init__.py'))
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def main():
    result_path = OUT/'final-green-v1.json'
    console_path = OUT/'final-green-v1-console.txt'
    if result_path.exists() or console_path.exists():
        raise RuntimeError('Final evidence must be fresh')
    before = inputs()
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'passed': False,
              'working_directory': str(ROOT), 'python': sys.executable,
              'scope': 'Full test_*.py unittest discovery; mocked CAD plus harmless Windows helper processes; no native CAD acceptance',
              'command': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'],
              'source_and_test_sha256': before, 'native_cad_test_executed': False,
              'actual_mr12_reservation_modified': False, 'production_runtime_deployed': False}
    started = time.monotonic()
    environment = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    completed = subprocess.run(report['command'], cwd=ROOT, env=environment,
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
    console = completed.stdout + completed.stderr
    console_path.write_text(console, encoding='utf-8')
    matches = re.findall(r'Ran (\d+) tests? in ([0-9.]+)s', console)
    if matches:
        report.update(test_count=int(matches[-1][0]), unittest_runtime_seconds=float(matches[-1][1]))
    report.update(exit_code=completed.returncode, elapsed_seconds=round(time.monotonic()-started, 3),
                  console=str(console_path.relative_to(ROOT)), console_sha256=digest(console_path),
                  source_and_tests_unchanged=(before == inputs()))
    diff = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True)
    report.update(diff_check_exit_code=diff.returncode, diff_check_output=diff.stdout+diff.stderr,
                  completed_at=datetime.now(timezone.utc).isoformat())
    report['passed'] = (completed.returncode == 0 and bool(matches)
                        and report['source_and_tests_unchanged'] and diff.returncode == 0)
    result_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in
        ('passed', 'test_count', 'unittest_runtime_seconds', 'source_and_tests_unchanged', 'diff_check_exit_code')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
