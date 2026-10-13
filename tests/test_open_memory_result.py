import unittest
from unittest.mock import MagicMock, patch
from solidworks_mcp.automation.documents import DocumentOperations
from solidworks_mcp.automation.base import SolidWorksAutomation


class Target(DocumentOperations, SolidWorksAutomation):
    pass


class OpenMemoryResultTests(unittest.TestCase):
    def instance(self):
        obj = object.__new__(Target)
        obj._target_pid = '123'
        obj._connected = True
        obj._sw_app = MagicMock()
        obj._sw_app.GetProcessID = 123
        obj._get_doc_title = lambda _: 'test'
        return obj

    def opened(self, action, events, errors):
        obj = self.instance()
        watcher = MagicMock(events=events, errors=errors)
        with patch('os.path.exists', return_value=True), \
             patch('solidworks_mcp.automation.memory_warning.MemoryWarningHandler', return_value=watcher):
            result = obj.open_document('C:/private/test.SLDASM', memory_warning_action=action)
        return result, obj

    def test_cancel_even_when_document_returned(self):
        result, obj = self.opened('cancel', [{'pid':123,'action':'cancel','closed':True}], [])
        self.assertFalse(result['success'])
        self.assertTrue(result['data']['operation_cancelled'])
        self.assertTrue(result['data']['document_returned'])
        obj._sw_app.CloseDoc.assert_not_called()
        obj._sw_app.ExitApp.assert_not_called()

    def test_explicit_continue_and_no_warning_remain_successful(self):
        self.assertTrue(self.opened('continue', [{'action':'continue'}], [])[0]['success'])
        self.assertTrue(self.opened('cancel', [], [])[0]['success'])

    def test_unconfirmed_dismissal_also_blocks_follow_up(self):
        self.assertFalse(self.opened('cancel', [{'action':'cancel','closed':False}], [])[0]['success'])

    def test_watcher_failure_is_not_reported_as_success(self):
        result, _ = self.opened('cancel', [], ['UIA failed'])
        self.assertFalse(result['success'])
        self.assertIn('UIA failed', result['data']['memory_warning_handler_errors'])
