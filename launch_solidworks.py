"""Guarded launcher and existing-PID verifier, also used by opt-in managed MCP."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
from contextlib import contextmanager

import win32api
import win32process
import win32event
import win32con
import win32file

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.utils import find_solidworks
from solidworks_mcp.desktop_process import start_desktop_process


def running_pids():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel.QueryFullProcessImageNameW
    query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                      ctypes.POINTER(wintypes.DWORD)]
    query.restype = wintypes.BOOL
    found = []
    for pid in win32process.EnumProcesses():
        try:
            handle = win32api.OpenProcess(0x1000, False, pid)
            try:
                buffer = ctypes.create_unicode_buffer(32768)
                length = wintypes.DWORD(len(buffer))
                if query(int(handle), 0, buffer, ctypes.byref(length)):
                    if Path(buffer.value).name.casefold() == 'sldworks.exe':
                        found.append(pid)
            finally:
                handle.Close()
        except win32api.error:
            continue
    return found


@contextmanager
def launcher_lock():
    mutex = win32event.CreateMutex(None, False, 'Local\\SolidWorksMCPLauncher')
    acquired = False
    try:
        status = win32event.WaitForSingleObject(mutex, 5000)
        acquired = status in (win32con.WAIT_OBJECT_0, win32con.WAIT_ABANDONED)
        if not acquired:
            raise RuntimeError('Another launcher is busy; no process was launched')
        yield
    finally:
        if acquired:
            win32event.ReleaseMutex(mutex)
        mutex.Close()


def launch(executable):
    with launcher_lock():
        return _launch_locked(executable)


def _launch_locked(executable):
    if len(running_pids()) >= 2:
        raise RuntimeError('Two or more SolidWorks instances already exist. '
                           'Use --pid for the intended instance; no process was launched.')
    executable = Path(executable).resolve(strict=True)
    if executable.name.casefold() != 'sldworks.exe':
        raise ValueError('Expected the installed SLDWORKS.exe')
    check_journal_available()
    return start_desktop_process(executable, executable.parent)


def check_journal_available():
    """Read-only preflight; never change per-user journal registry settings."""
    import winreg
    roots = Path(os.environ['APPDATA']) / 'SOLIDWORKS'
    candidates = set(roots.glob('SOLIDWORKS */swxJRNL.swj'))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\SolidWorks') as root:
            for index in range(winreg.QueryInfoKey(root)[0]):
                version = winreg.EnumKey(root, index)
                if not version.upper().startswith('SOLIDWORKS '):
                    continue
                try:
                    with winreg.OpenKey(root, version + r'\ExtReferences') as refs:
                        folders, _ = winreg.QueryValueEx(refs, 'SolidWorks Journal Folders')
                        for folder in folders.split(';'):
                            if folder:
                                candidates.add(Path(os.path.expandvars(folder)) / 'swxJRNL.swj')
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass
    for path in candidates:
        if not path.exists():
            continue
        try:
            handle = win32file.CreateFile(str(path), win32con.GENERIC_READ, 0,
                                         None, win32con.OPEN_EXISTING, 0, None)
        except win32api.error as exc:
            raise RuntimeError(f'Journal file unavailable: {path} (Windows error {exc.winerror}). '
                               'No process was launched. PID isolation does not isolate '
                               'per-user journal/AutoRecover files.') from exc
        else:
            handle.Close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pid', type=int, help='Verify an existing instance without launching')
    mode.add_argument('--launch', action='store_true', help='Explicitly request one new instance')
    parser.add_argument('--exe', help='Installed SLDWORKS.exe path (optional)')
    parser.add_argument('--output', type=Path, help='Write the verified connection manifest')
    args = parser.parse_args()
    pid = args.pid
    if args.launch:
        executable = args.exe or find_solidworks()
        if not executable:
            raise RuntimeError('SolidWorks installation not found; no process was launched')
        pid = launch(executable)
        print(f'Launched one instance: PID {pid}', flush=True)
    if not pid or pid <= 0:
        raise ValueError('A positive PID is required')
    os.environ['SOLIDWORKS_TARGET_PID'] = str(pid)
    automation = SolidWorksAutomation()
    try:
        deadline = time.monotonic() + (60 if args.launch else 0)
        while True:
            result = automation.connect()
            if result['success'] or time.monotonic() >= deadline:
                break
            time.sleep(0.5)
        if not result['success']:
            raise RuntimeError(f'PID {pid}: {result["message"]}. '
                               'No alternate instance was launched; inspect this instance.')
        if args.launch:
            automation.app.UserControl = True
            automation.app.Visible = True
        root = Path(__file__).resolve().parent
        manifest = {'pid': pid, 'command': str(root/'.venv/Scripts/python.exe'),
                    'args': [str(root/'solidworks_mcp_server.py')],
                    'env': {'SOLIDWORKS_TARGET_PID': str(pid),
                            'SOLIDWORKS_MCP_LOG': str(root/f'test-results/session-{pid}-{{server_pid}}.log')}}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(json.dumps(manifest, indent=2))
    finally:
        automation.disconnect()


if __name__ == '__main__':
    main()
