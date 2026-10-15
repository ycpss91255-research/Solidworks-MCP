"""Built-in document-save fallbacks must stop on a native CAD fault; no real CAD."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import pywintypes
from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.native_fault import FaultStore


class DocumentNativeSaveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        identity = patch('solidworks_mcp.automation.managed_session.process_identity', return_value='save-fixture-created')
        identity.start(); self.addCleanup(identity.stop)
        self.a = SolidWorksAutomation()
        self.a._target_pid = '123'; self.a._configured_target = '123'
        self.a._auto_launch = False; self.a._connected = True
        self.a._bound_identity = 'save-fixture-created'
        self.a._recovery_startup_enabled = False
        self.a._fault_store = FaultStore(self.root/'faults')
        self.doc = Mock()
        self.doc.SaveAs.side_effect = TypeError('ordinary binding mismatch')
        self.doc.Extension.SaveAs.side_effect = TypeError('ordinary binding mismatch')
        self.doc.Extension.SaveAs2.return_value = True
        self.a.get_active_doc = Mock(return_value=(self.doc, None))
        self.error = pywintypes.com_error(-2147417851, 'synthetic native server fault', None, None)
        self.destination = str(self.root/'private-copy.sldasm')

    def check_fault_result(self, result):
        self.assertFalse(result['success'])
        self.assertTrue(result.get('data', {}).get('native_fault_quarantined'))
        fault = self.a._fault_store.read(123, lambda pid: 'save-fixture-created')
        self.assertIsNotNone(fault)
        self.assertEqual(fault['hresult'], -2147417851)

    def test_native_saveas_fault_does_not_call_either_fallback(self):
        self.doc.SaveAs.side_effect = self.error
        result = self.a.save_document(self.destination)
        self.doc.Extension.SaveAs.assert_not_called()
        self.doc.Extension.SaveAs2.assert_not_called()
        self.check_fault_result(result)

    def test_native_extension_saveas_fault_does_not_call_saveas2(self):
        self.doc.Extension.SaveAs.side_effect = self.error
        result = self.a.save_document(self.destination)
        self.doc.Extension.SaveAs2.assert_not_called()
        self.check_fault_result(result)

    def test_native_final_saveas_fault_keeps_identity_bound_evidence(self):
        self.doc.Extension.SaveAs2.side_effect = self.error
        result = self.a.save_document(self.destination)
        self.check_fault_result(result)

    def test_ordinary_binding_failures_can_still_use_final_fallback(self):
        result = self.a.save_document(self.destination)
        self.assertTrue(result['success'])
        self.doc.Extension.SaveAs2.assert_called_once()
        self.assertIsNone(self.a._fault_store.read(123, lambda pid: 'save-fixture-created'))


if __name__ == '__main__':
    unittest.main()
