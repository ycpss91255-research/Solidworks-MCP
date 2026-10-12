import unittest
from unittest.mock import patch
from solidworks_mcp.automation.journal_warning import JournalWarningHandler, matches_journal_warning


class JournalWarningTests(unittest.TestCase):
    def test_exact_warning_and_unrelated_dialogs(self):
        self.assertTrue(matches_journal_warning('SOLIDWORKS 無法產生日誌檔案。自動復原無法運作。'))
        self.assertTrue(matches_journal_warning('SOLIDWORKS A journal file could not be created. Auto recover will not work.'))
        for text in ('SOLIDWORKS save changes?', 'SOLIDWORKS critically low on memory',
                     'SOLIDWORKS Unable to locate the graphics registry file', 'other app 無法產生日誌檔案 自動復原'):
            self.assertFalse(matches_journal_warning(text))

    def candidate(self, pid=123, buttons=None):
        handler = JournalWarningHandler(123)
        with patch.object(handler, '_alive', return_value=True), \
             patch('win32process.GetWindowThreadProcessId', return_value=(1,pid)), \
             patch('win32gui.IsWindowVisible', return_value=True), \
             patch('win32gui.GetClassName', return_value='#32770'), \
             patch('win32gui.GetWindowText', return_value='SOLIDWORKS'), \
             patch.object(handler, '_dialog_content', return_value=('SOLIDWORKS 無法產生日誌檔案 自動復原', buttons if buttons is not None else {1})):
            return handler._candidate(1)

    def test_target_ok_button_only(self):
        self.assertEqual(self.candidate(), 1)
        self.assertEqual(self.candidate(buttons={2}), 2)
        self.assertIsNone(self.candidate(pid=456))
        self.assertIsNone(self.candidate(buttons={6,7}))
        self.assertIsNone(self.candidate(buttons={1,2}))
