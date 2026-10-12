"""Explicitly authorized dismissal of one PID-scoped startup journal warning."""
import win32gui
import win32con
import win32process
from .memory_warning import MemoryWarningHandler


def matches_journal_warning(text):
    text = text.casefold()
    return 'solidworks' in text and (
        ('無法產生日誌檔案' in text and '自動復原' in text) or
        ('无法产生日志' in text and '自动恢复' in text) or
        ('无法创建日志' in text and '自动恢复' in text) or
        ('a journal file could not be created' in text and 'auto recover' in text))


class JournalWarningHandler(MemoryWarningHandler):
    button_ids = (1,)

    def __init__(self, pid, timeout=30):
        super().__init__(pid, 'continue', timeout)
        self.action = 'dismiss_journal'

    def _candidate(self, hwnd):
        if not self._alive() or win32process.GetWindowThreadProcessId(hwnd)[1] != self.pid:
            return None
        if not win32gui.IsWindowVisible(hwnd) or win32gui.GetClassName(hwnd) != '#32770':
            return None
        if win32gui.GetWindowText(hwnd).strip().casefold() != 'solidworks':
            return None
        text, buttons = self._dialog_content(hwnd)
        if matches_journal_warning(text) and buttons in ({1},{2}):
            return next(iter(buttons))
        return None

    def _dialog_content(self, hwnd):
        text, buttons = super()._dialog_content(hwnd)
        # Traditional SW 2023 MessageBox: OK is AutomationId/control ID 2.
        # Verify the native child instead of assuming task-dialog button IDs.
        child = win32gui.GetDlgItem(hwnd, 2)
        if child and win32gui.GetClassName(child) == 'Button' and win32gui.IsWindowEnabled(child):
            label = win32gui.GetWindowText(child).replace('&','').strip().casefold()
            if label in ('確定','确定','ok'):
                buttons.add(2)
        return text, buttons

    def _click_button(self, hwnd, button):
        if button == 2:
            child = win32gui.GetDlgItem(hwnd, 2)
            win32gui.PostMessage(child, win32con.BM_CLICK, 0, 0)
        else:
            super()._click_button(hwnd, button)
