import os
import unittest
from unittest.mock import Mock, MagicMock, patch
from solidworks_mcp.automation.base import SolidWorksAutomation
from solidworks_mcp.automation.journal_warning import JournalWarningHandler


class JournalHookTests(unittest.TestCase):
    def instance(self):
        obj = object.__new__(SolidWorksAutomation)
        obj._target_pid = '123'
        obj._journal_warning_handler = None
        return obj

    def test_attach_reuses_hook_and_disconnect_stops_it(self):
        obj = self.instance()
        handler = MagicMock(pid=123, events=[], errors=[])
        handler.thread.is_alive.return_value = True
        with patch.dict(os.environ, {'SOLIDWORKS_JOURNAL_WARNING_ACTION': 'dismiss'}), \
             patch('solidworks_mcp.automation.managed_session.process_identity', return_value='created'), \
             patch('solidworks_mcp.automation.journal_warning.JournalWarningHandler', return_value=handler) as create:
            self.assertIs(obj._ensure_journal_warning_hook(), handler)
            self.assertIs(obj._ensure_journal_warning_hook(), handler)
            create.assert_called_once_with(123, timeout=None)
            obj._target_com_initialized = False
            obj.disconnect()
            handler.__exit__.assert_called_once()

    def test_manual_never_starts_hook(self):
        with patch.dict(os.environ, {'SOLIDWORKS_JOURNAL_WARNING_ACTION': 'manual'}), \
             patch('solidworks_mcp.automation.journal_warning.JournalWarningHandler') as create:
            self.assertIsNone(self.instance()._ensure_journal_warning_hook())
            create.assert_not_called()

    def test_pid_change_stops_previous_hook(self):
        obj = self.instance()
        old = MagicMock(pid=456)
        obj._journal_warning_handler = old
        with patch.dict(os.environ, {'SOLIDWORKS_JOURNAL_WARNING_ACTION': 'manual'}):
            obj._ensure_journal_warning_hook()
        old.__exit__.assert_called_once()

    def test_continuous_watcher_handles_second_late_dialog(self):
        handler = JournalWarningHandler(123, timeout=None)
        cycles = [0]
        def enumerate_windows(callback, arg):
            # Second warning arrives long after the first was closed.
            if cycles[0] in (0, 8):
                callback(100 + cycles[0], arg)
            cycles[0] += 1
        def wait(_):
            if cycles[0] >= 10:
                handler.stop.set()
            return False
        with patch.object(handler, '_alive', return_value=True), \
             patch.object(handler, '_candidate', return_value=2), \
             patch.object(handler, '_click_button') as click, \
             patch.object(handler.stop, 'wait', side_effect=wait), \
             patch('win32gui.EnumWindows', side_effect=enumerate_windows), \
             patch('win32gui.IsWindow', return_value=False):
            handler._watch()
        self.assertEqual(click.call_count, 2)
        self.assertEqual(len(handler.events), 2)
        self.assertTrue(all(event['closed'] for event in handler.events))


if __name__ == '__main__':
    unittest.main()
