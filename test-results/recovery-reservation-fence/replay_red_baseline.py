"""Freeze and replay three real regressions against the actual Git base source.

No CAD: the selected production tests mock identity/locks/launcher. The baseline
modules are loaded only in this disposable Python interpreter, never deployed.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
BASE = '5793bcf17f0d8697a469b66c6e66cb4e854af04f'
sys.path.insert(0, str(ROOT))
import solidworks_mcp

sources = {}
for name in ('recovery_monitor', 'recovery_service'):
    relative = f'solidworks_mcp/{name}.py'
    data = subprocess.run(['git', 'show', f'{BASE}:{relative}'], cwd=ROOT,
                          capture_output=True, check=True).stdout
    path = OUT / f'red-baseline-{name}.py'
    path.write_bytes(data)
    sources[str(path)] = hashlib.sha256(data).hexdigest()
    qualified = f'solidworks_mcp.{name}'
    spec = importlib.util.spec_from_file_location(qualified, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    setattr(solidworks_mcp, name, module)
    spec.loader.exec_module(module)

test_source = ROOT / 'tests/test_recovery_startup_fence.py'
test_snapshot = OUT / 'red-regression-tests.py'
test_snapshot.write_bytes(test_source.read_bytes())
sources[str(test_snapshot)] = hashlib.sha256(test_snapshot.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('red_regression_tests', test_snapshot)
tests = importlib.util.module_from_spec(spec); spec.loader.exec_module(tests)
names = ['test_known_dead_stale_claim_is_archived_then_retried',
         'test_immediate_launch_failure_can_retry_without_creator_exit',
         'test_startup_arguments_pin_expected_identity']
suite = unittest.TestSuite(tests.StartupFenceTests(name) for name in names)
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
(OUT / 'red-frozen-replay.txt').write_text(stream.getvalue(), encoding='utf-8')
failed = [test._testMethodName for test, _ in result.failures + result.errors]
report = {'base_commit': BASE, 'tests_run': result.testsRun, 'expected_red_cases': names,
          'observed_failing_cases': failed, 'expected_red_reproduced': sorted(failed) == sorted(names),
          'source_sha256': sources, 'live_runtime_modified': False, 'cad_called': False}
(OUT / 'red-frozen-replay.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['expected_red_reproduced'] else 1)
