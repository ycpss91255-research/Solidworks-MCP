"""Bounded, PID-scoped handling of SolidWorks' low-memory task dialog."""
import logging
import threading
import time
import importlib.util

import win32api
import win32con
import win32event
import win32gui
import win32process

logger = logging.getLogger(__name__)


def matches_warning(text):
    text = text.casefold()
    return 'solidworks' in text and (
        'rm_commitcharge' in text or
        '記憶體嚴重不足' in text or
        '内存严重不足' in text or
        'critically low on memory' in text)


class MemoryWarningHandler:
    """Watch only during one open operation; never use global keyboard input."""
    def __init__(self, pid, action, timeout=30):
        if action not in ('continue', 'cancel'):
            raise ValueError('Unknown memory warning action')
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError('A positive target PID is required')
        if importlib.util.find_spec('comtypes') is None:
            raise ImportError('Automatic memory warning handling requires comtypes')
        self.pid, self.action, self.timeout = pid, action, timeout
        self.events = []
        self.errors = []
        self.stop = threading.Event()
        self.thread = None
        self.process = None

    def __enter__(self):
        # Hold a process handle so an exited/reused PID cannot be targeted.
        self.process = win32api.OpenProcess(
            win32con.SYNCHRONIZE | win32con.PROCESS_QUERY_INFORMATION, False, self.pid)
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()
        self.process.Close()

    def _alive(self):
        return win32event.WaitForSingleObject(self.process, 0) == win32con.WAIT_TIMEOUT

    def _candidate(self, hwnd):
        if not self._alive() or win32process.GetWindowThreadProcessId(hwnd)[1] != self.pid:
            return None
        if not win32gui.IsWindowVisible(hwnd) or win32gui.GetClassName(hwnd) != '#32770':
            return None
        if win32gui.GetWindowText(hwnd).strip().casefold() != 'solidworks':
            return None
        text, buttons = self._dialog_content(hwnd)
        if not matches_warning(text):
            return None
        # Verify the task dialog exposes both standard Yes and No buttons.
        if 6 not in buttons or 7 not in buttons:
            return None
        return 6 if self.action == 'continue' else 7

    def _dialog_content(self, hwnd):
        element = self._uia.ElementFromHandle(hwnd)
        if element.CurrentProcessId != self.pid:
            return '', set()
        elements = element.FindAll(4, self._uia.CreateTrueCondition())  # descendants
        names, buttons = [], set()
        for index in range(elements.Length):
            child = elements.GetElement(index)
            if child.CurrentProcessId != self.pid:
                continue
            names.append(child.CurrentName or '')
            if child.CurrentControlType == 50000:  # UIA_ButtonControlTypeId
                identity = child.CurrentAutomationId
                if identity in ('CommandButton_6', 'CommandButton_7'):
                    if child.CurrentIsEnabled:
                        buttons.add(int(identity.rsplit('_', 1)[1]))
        return '\n'.join(names), buttons

    def _watch(self):
        deadline = time.monotonic() + self.timeout
        import pythoncom
        pythoncom.CoInitialize()
        try:
            import comtypes.client
            module = comtypes.client.GetModule('UIAutomationCore.dll')
            self._uia = comtypes.client.CreateObject(
                '{FF48DBA4-60EF-4201-AA87-54103EEF594E}', interface=module.IUIAutomation)
            while not self.stop.is_set() and time.monotonic() < deadline and self._alive():
                windows = []
                win32gui.EnumWindows(lambda hwnd, _: (windows.append(hwnd), True)[1], None)
                for hwnd in windows:
                    if self.stop.is_set():
                        return
                    try:
                        button = self._candidate(hwnd)
                        if button is None:
                            continue
                        # Recheck process and dialog immediately before the action.
                        if self.stop.is_set() or self._candidate(hwnd) != button:
                            continue
                        # Documented task-dialog API: TDM_CLICK_BUTTON = WM_USER+102.
                        win32gui.PostMessage(hwnd, win32con.WM_USER + 102, button, 0)
                        event = {'pid': self.pid, 'action': self.action, 'button_id': button,
                                 'closed': False}
                        self.events.append(event)
                        logger.warning('Handled SolidWorks low-memory warning: %s', event)
                        while time.monotonic() < deadline:
                            if not win32gui.IsWindow(hwnd):
                                event['closed'] = True
                                break
                            if self.stop.wait(0.05):
                                event['closed'] = not win32gui.IsWindow(hwnd)
                                break
                        return  # At most one warning per open operation.
                    except win32gui.error:
                        continue  # A window may disappear during enumeration.
                self.stop.wait(0.1)
        except Exception as exc:
            self.errors.append(str(exc))
            logger.exception('Memory warning watcher failed')
        finally:
            self._uia = None
            pythoncom.CoUninitialize()
