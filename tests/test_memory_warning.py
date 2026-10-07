import unittest
from unittest.mock import patch
from solidworks_mcp.automation.memory_warning import MemoryWarningHandler, matches_warning


class WarningTests(unittest.TestCase):
    def test_only_known_memory_warning_matches(self):
        self.assertTrue(matches_warning('SOLIDWORKS 記憶體嚴重不足 是否要繼續'))
        self.assertTrue(matches_warning('SOLIDWORKS critically low on memory'))
        for text in ('SOLIDWORKS 無法產生日誌檔案', 'SOLIDWORKS save changes?',
                     'Another app critically low on memory'):
            self.assertFalse(matches_warning(text))

    def candidate(self, pid=123, text='SOLIDWORKS 記憶體嚴重不足', buttons=True):
        handler = MemoryWarningHandler(123, 'continue')
        with patch.object(handler, '_alive', return_value=True), \
             patch('win32process.GetWindowThreadProcessId', return_value=(1, pid)), \
             patch('win32gui.IsWindowVisible', return_value=True), \
             patch('win32gui.GetClassName', side_effect=lambda h: '#32770' if h==1 else ('Static' if h==10 else 'Button')), \
             patch('win32gui.GetWindowText', side_effect=lambda h: 'SOLIDWORKS' if h==1 else (text if h==10 else '')), \
             patch.object(handler, '_dialog_content', return_value=(text, {6,7} if buttons else {6})):
            return handler._candidate(1)

    def test_target_dialog(self):
        self.assertEqual(self.candidate(), 6)

    def test_unrelated_pid_is_rejected(self):
        self.assertIsNone(self.candidate(pid=456))

    def test_other_dialog_is_rejected(self):
        self.assertIsNone(self.candidate(text='SOLIDWORKS save changes?'))

    def test_ambiguous_buttons_are_rejected(self):
        self.assertIsNone(self.candidate(buttons=False))

    def test_exited_process_is_rejected_before_enumeration(self):
        handler = MemoryWarningHandler(123, 'cancel')
        with patch.object(handler, '_alive', return_value=False), patch('win32process.GetWindowThreadProcessId') as query:
            self.assertIsNone(handler._candidate(1))
            query.assert_not_called()

if __name__ == '__main__':
    unittest.main()
