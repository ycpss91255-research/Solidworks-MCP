import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import pywintypes
from solidworks_mcp import server


class ExecutionFailureEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.fake = Mock(is_connected=True, _target_pid=123)
        self.fake.app.ActiveDoc = None

    def execute(self, source, trace_directory=''):
        with patch.object(server, 'sw_automation', self.fake), \
             patch.dict(os.environ, {'SOLIDWORKS_SCRIPT_TRACE_DIR': trace_directory}), \
             self.assertLogs('SolidWorksMCP', level='ERROR') as captured:
            result = server._execute_python_fixed(source)
        return result, '\n'.join(captured.output)

    def test_native_fault_records_hresult_pid_and_partial_output_without_trace_opt_in(self):
        fault = pywintypes.com_error(-2147417851, 'The server threw an exception', None, None)
        self.fake.app.CloseAllDocuments.side_effect = fault
        before = sys.stdout, sys.stderr
        result, log = self.execute("print('SAVED all private documents')\nimport sys\nprint('before batch close',file=sys.stderr)\nsw.CloseAllDocuments(True)")
        self.assertFalse(result['success'])
        self.assertEqual(result['data']['solidworks_pid'], 123)
        self.assertEqual(result['data']['hresult'], -2147417851)
        self.assertEqual(result['data']['script_line'], 4)
        self.assertEqual(result['data']['script_source_line'], 'sw.CloseAllDocuments(True)')
        self.assertIn('SAVED all private documents', result['data']['stdout'])
        self.assertIn('before batch close', result['data']['stderr'])
        self.assertIn('CloseAllDocuments', log)
        self.assertIn('-2147417851', log)
        self.assertIn('123', log)
        self.assertIn('SAVED all private documents', log)
        self.assertIn('before batch close', log)
        self.assertIs(sys.stdout, before[0])
        self.assertIs(sys.stderr, before[1])
        self.fake.connect.assert_not_called()
        self.fake.app.CloseAllDocuments.assert_called_once_with(True)

    def test_python_binding_failure_is_distinguishable_from_native_fault(self):
        result, log = self.execute("print('before bad binding')\nraise TypeError('invalid array binding')")
        self.assertEqual(result['data']['error_type'], 'TypeError')
        self.assertIsNone(result['data']['hresult'])
        self.assertIn('invalid array binding', log)
        self.assertIn('before bad binding', log)

    def test_pre_execution_com_fault_does_not_need_capture_context_to_exist(self):
        from unittest.mock import PropertyMock
        type(self.fake.app).ActiveDoc = PropertyMock(side_effect=pywintypes.com_error(-2147023170, 'RPC failed', None, None))
        result, log = self.execute("raise AssertionError('must not execute')")
        self.assertEqual(result['data']['hresult'], -2147023170)
        self.assertEqual(result['data']['stdout'], '')
        self.assertIn('RPC failed', log)

    def test_optional_trace_filename_still_identifies_the_user_call(self):
        with tempfile.TemporaryDirectory() as directory:
            result, log = self.execute("print('traced checkpoint')\n1/0", directory)
        self.assertEqual(result['data']['script_line'], 2)
        self.assertEqual(result['data']['script_source_line'], '1/0')
        self.assertIn('traced checkpoint', log)

    def test_syntax_failure_is_logged_and_preserves_existing_details(self):
        result, log = self.execute('def invalid(')
        self.assertEqual(result['data']['error_type'], 'SyntaxError')
        self.assertIn('never closed', result['data']['details'])
        self.assertIn('SyntaxError', log)


if __name__ == '__main__':
    unittest.main()
