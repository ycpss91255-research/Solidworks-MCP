"""Explicitly authorized dismissal of one PID-scoped startup journal warning."""
import win32gui
import win32con
import win32process
import logging
import time
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

    def _click_button(self, hwnd, button):
        child = win32gui.GetDlgItem(hwnd, button)
        win32gui.PostMessage(child, win32con.BM_CLICK, 0, 0)

    def _watch(self):
        """Native dialog watcher; timeout=None means the connection lifetime."""
        deadline = float('inf') if self.timeout is None else time.monotonic() + self.timeout
        pending = {}
        try:
            while not self.stop.is_set() and self._alive() and time.monotonic() < deadline:
                for hwnd, event in list(pending.items()):
                    if not win32gui.IsWindow(hwnd):
                        event['closed'] = True
                        pending.pop(hwnd)
                        logging.getLogger(__name__).info('Journal warning closed: %s', event)
                windows = []
                win32gui.EnumWindows(lambda hwnd, _: (windows.append(hwnd), True)[1], None)
                for hwnd in windows:
                    if self.stop.is_set():
                        break
                    try:
                        button = self._candidate(hwnd)
                        if button is None or hwnd in pending:
                            continue
                        if self.stop.is_set() or self._candidate(hwnd) != button:
                            continue
                        self._click_button(hwnd, button)
                        event = {'pid': self.pid, 'action': self.action,
                                 'button_id': button, 'closed': False}
                        self.events.append(event)
                        pending[hwnd] = event
                        logging.getLogger(__name__).warning('Journal warning dismissal sent: %s', event)
                    except win32gui.error:
                        continue
                self.stop.wait(0.2)
        except Exception as exc:
            self.errors.append(str(exc))
            logging.getLogger(__name__).exception('Journal warning watcher failed')

    def _dialog_content(self, hwnd):
        # This warning is a native MessageBox. Avoid UIA/COM calls that can block
        # behind the same modal dialog they are intended to dismiss.
        names, buttons = [], set()
        def child_content(child, _):
            if win32process.GetWindowThreadProcessId(child)[1] != self.pid:
                return True
            names.append(win32gui.GetWindowText(child))
            if win32gui.GetClassName(child) == 'Button' and win32gui.IsWindowEnabled(child):
                label = win32gui.GetWindowText(child).replace('&', '').strip().casefold()
                control = win32gui.GetDlgCtrlID(child)
                if label in ('確定', '确定', 'ok') and control in (1, 2):
                    buttons.add(control)
                else:
                    buttons.add(-1)  # Refuse dialogs exposing other actions.
            return True
        win32gui.EnumChildWindows(hwnd, child_content, None)
        return '\n'.join(names), buttons
