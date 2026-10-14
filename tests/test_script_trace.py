import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import os
from unittest.mock import Mock, patch
from solidworks_mcp.script_trace import ScriptTrace, memory_snapshot


class ScriptTraceTests(unittest.TestCase):
    def test_generated_external_code_is_excluded_but_user_exec_is_traced(self):
        generated = {}
        exec(compile('def generated():\n x=1\n return x', '<string>', 'exec'), generated)
        with tempfile.TemporaryDirectory() as directory:
            with ScriptTrace("generated()\nexec('y=2')", 123, directory) as trace:
                exec(trace.compiled, generated)
            rows = [json.loads(x) for x in next(Path(directory).glob('*.jsonl')).read_text().splitlines()]
            dynamic = [x for x in rows if x.get('filename') == '<string>' and x['event']=='line']
            self.assertEqual([x['line'] for x in dynamic], [1])
    def test_exception_preserves_last_line_and_restores_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = sys.gettrace()
            with self.assertRaises(ZeroDivisionError):
                with ScriptTrace('x=1\ny=1/0', 123, directory) as trace:
                    exec(trace.compiled, {})
            self.assertIs(sys.gettrace(), previous)
            rows = [json.loads(x) for x in next(Path(directory).glob('*.jsonl')).read_text().splitlines()]
            self.assertEqual(rows[-1]['event'], 'failed')
            self.assertEqual([x['line'] for x in rows if x['event']=='line'], [1, 2])
            self.assertTrue(all(x['solidworks_pid']==123 for x in rows))

    def test_abrupt_child_exit_keeps_breadcrumb(self):
        with tempfile.TemporaryDirectory() as directory:
            child = ('from solidworks_mcp.script_trace import ScriptTrace\n'
                     f'with ScriptTrace("import os\\nos._exit(23)",123,{directory!r}) as trace:\n'
                     ' exec(trace.compiled,{})')
            result = subprocess.run([sys.executable, '-c', child], timeout=10)
            self.assertEqual(result.returncode, 23)
            rows = [json.loads(x) for x in next(Path(directory).glob('*.jsonl')).read_text().splitlines()]
            self.assertEqual(rows[-1]['event'], 'line')
            self.assertEqual(rows[-1]['line'], 2)

    def test_metrics_and_absolute_directory(self):
        value = memory_snapshot()
        self.assertGreater(value['commit_limit_bytes'], 0)
        self.assertGreater(value['commit_bytes'], 0)
        with self.assertRaises(ValueError):
            ScriptTrace('pass', 123, 'relative')

    def test_execute_python_opt_in_preserves_result_without_cad(self):
        from solidworks_mcp import server
        fake = Mock(is_connected=True, _target_pid='123')
        fake.app.ActiveDoc = None
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(server, 'sw_automation', fake), \
             patch.dict(os.environ, {'SOLIDWORKS_SCRIPT_TRACE_DIR': directory}):
            result = server._execute_python_fixed("print('diagnostic')\nresult=42")
            self.assertTrue(result['success'])
            self.assertEqual(result['data']['result'], '42')
            self.assertIn('diagnostic', result['data']['stdout'])
            rows = [json.loads(x) for x in next(Path(directory).glob('*.jsonl')).read_text().splitlines()]
            self.assertEqual(rows[-1]['event'], 'completed')
            fake.connect.assert_not_called()
