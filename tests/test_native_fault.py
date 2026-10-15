import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import Mock, PropertyMock, patch

import pywintypes
from solidworks_mcp.native_fault import FaultStore, native_hresult
from solidworks_mcp.automation.base import SolidWorksAutomation
from solidworks_mcp import server


class NativeFaultStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = FaultStore(self.root)
        self.error = pywintypes.com_error(-2147417851, 'server fault', None, None)

    def test_persisted_fault_blocks_same_identity_in_another_store_instance(self):
        self.store.record(123, 'created-a', self.error)
        other = FaultStore(self.root)
        fault = other.read(123, lambda pid: 'created-a')
        self.assertEqual(fault['hresult'], -2147417851)
        self.assertEqual(fault['pid'], 123)

    def test_different_pid_or_reused_identity_is_not_quarantined(self):
        self.store.record(123, 'created-a', self.error)
        self.assertIsNone(self.store.read(124, lambda pid: 'created-a'))
        self.assertIsNone(self.store.read(123, lambda pid: 'created-b'))
        self.assertIsNone(self.store.read(123, lambda pid: None))

    def test_first_fault_evidence_is_preserved_for_same_process(self):
        self.store.record(123, 'created-a', self.error)
        self.store.record(123, 'created-a', pywintypes.com_error(-2147023170, 'later RPC error', None, None))
        self.assertEqual(self.store.read(123, lambda pid: 'created-a')['hresult'], -2147417851)

    def test_python_binding_and_busy_errors_do_not_create_a_marker(self):
        for error in (TypeError('binding'), pywintypes.com_error(-2147418111, 'call rejected', None, None)):
            self.assertIsNone(native_hresult(error))
            self.assertIsNone(self.store.record(123, 'created-a', error))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unknown_creation_identity_cannot_quarantine_a_reused_pid(self):
        with self.assertRaises(ValueError):
            self.store.record(123, None, self.error)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_malformed_marker_is_not_treated_as_healthy(self):
        self.store.record(123, 'created-a', self.error)
        marker = next(self.root.glob('*.json'))
        marker.write_text('{broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.read(123, lambda pid: 'created-a')

    def test_recording_new_identity_replaces_only_its_pid_marker(self):
        self.store.record(123, 'created-a', self.error)
        self.store.record(124, 'created-other', self.error)
        self.store.record(123, 'created-b', self.error)
        self.assertEqual(self.store.read(123, lambda pid: 'created-b')['start_time'], 'created-b')
        self.assertIsNotNone(self.store.read(124, lambda pid: 'created-other'))

    def test_separate_interpreter_reads_persisted_evidence(self):
        self.store.record(123, 'created-a', self.error)
        code = "import sys,json;from solidworks_mcp.native_fault import FaultStore;print(json.dumps(FaultStore(sys.argv[1]).read(123,lambda pid:'created-a')))"
        result = subprocess.run([sys.executable, '-c', code, str(self.root)],
                                capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)['hresult'], -2147417851)

    def test_explicit_snapshot_cause_preserves_native_hresult(self):
        from solidworks_mcp.recovery_snapshot import SnapshotError
        wrapped = SnapshotError('copy failed', {})
        wrapped.__cause__ = self.error
        self.assertEqual(native_hresult(wrapped), -2147417851)


class NativeFaultBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.store = FaultStore(Path(self.temporary.name))
        self.identity = patch('solidworks_mcp.automation.managed_session.process_identity', return_value='created-a')
        self.reader = self.identity.start(); self.addCleanup(self.identity.stop)
        self.error = pywintypes.com_error(-2147417851, 'server fault', None, None)
        self.instance = self.automation()

    def automation(self):
        instance = SolidWorksAutomation()
        instance._target_pid = '123'; instance._configured_target = '123'
        instance._auto_launch = False; instance._connected = True
        instance._bound_identity = 'created-a'; instance._fault_store = self.store
        instance._recovery_startup_enabled = False
        instance._sw_app = Mock()
        instance._sw_app.ActiveDoc = None
        return instance

    def execute(self, source, instance=None):
        with patch.object(server, 'sw_automation', instance or self.instance), \
             patch.dict('os.environ', {'SOLIDWORKS_SCRIPT_TRACE_DIR': ''}):
            return server._execute_python_fixed(source)

    def test_next_script_stops_before_any_cad_call_after_native_failure(self):
        self.instance.app.CloseDoc.side_effect = self.error
        first = self.execute("sw.CloseDoc('private')")
        self.assertFalse(first['success'])
        second = self.execute('sw.Save3()')
        self.assertFalse(second['success'])
        self.instance.app.Save3.assert_not_called()
        self.assertTrue(second['data']['native_fault_quarantined'])

    def test_python_error_does_not_block_next_script(self):
        self.assertFalse(self.execute("raise TypeError('binding')")['success'])
        self.assertTrue(self.execute('result=42')['success'])

    def test_restart_and_recovery_connection_stop_before_revision_probe(self):
        self.store.record(123, 'created-a', self.error)
        another = self.automation()
        with patch.object(type(another.app), 'RevisionNumber', create=True,
                          new_callable=PropertyMock) as revision:
            self.assertFalse(another.is_connected)
            revision.assert_not_called()
        with patch.object(another, '_connect_target') as attach, patch.object(another, '_ensure_journal_warning_hook') as hook:
            self.assertFalse(another.connect()['success'])
        attach.assert_not_called(); hook.assert_not_called()

    def test_builtin_exception_result_records_native_failure(self):
        try:
            raise self.error
        except Exception:
            self.instance._result(False, 'close failed')
        self.assertIsNotNone(self.store.read(123, self.reader))

    def test_managed_start_is_allowed_only_after_faulted_target_exits(self):
        self.store.record(123, 'created-a', self.error)
        self.instance._auto_launch = True
        self.reader.return_value = None
        expected = {'success': True, 'data': {'pid': 456}}
        with patch('solidworks_mcp.automation.managed_session.connect_managed', return_value=expected) as managed:
            self.assertTrue(self.instance.connect()['success'])
        managed.assert_called_once()

    def test_unreadable_marker_fails_closed_before_connect_hook(self):
        with patch.object(self.store, 'read', side_effect=PermissionError('unreadable state')), \
             patch.object(self.instance, '_connect_target') as attach, \
             patch.object(self.instance, '_ensure_journal_warning_hook') as hook:
            self.assertFalse(self.instance.connect()['success'])
        attach.assert_not_called(); hook.assert_not_called()

    def test_exited_bound_process_does_not_get_a_com_health_probe(self):
        self.reader.return_value = None
        with patch.object(type(self.instance.app), 'RevisionNumber', create=True,
                          new_callable=PropertyMock) as revision:
            self.assertFalse(self.instance.is_connected)
            revision.assert_not_called()

    def test_builtin_tool_dispatch_is_blocked_without_entering_document_method(self):
        import asyncio
        self.store.record(123, 'created-a', self.error)
        with patch.object(server, 'sw_automation', self.instance), \
             patch.object(self.instance, 'get_active_doc') as document:
            result = asyncio.run(server.call_tool('get_document_info', {}))
        document.assert_not_called()
        self.assertIn('native_fault_quarantined', result[0].text)


if __name__ == '__main__':
    unittest.main()
