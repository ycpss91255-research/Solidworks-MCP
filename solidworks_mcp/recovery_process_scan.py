"""Conservative, read-only inventory of recovery launcher/worker processes.

An empty result is usable only while the caller holds this session's launch
and monitor mutexes. It is not permission to kill a process or delete a file.
The two snapshots and held handles cover a venv launcher exiting while its
real worker starts; any incomplete or changing observation fails closed.
"""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ctypes
from ctypes import wintypes
import re
import sys

import win32api
import win32con
import win32event


class RecoveryInventoryUncertain(RuntimeError):
    pass


_PYTHON_NAME = re.compile(r'^(?:pythonw?[0-9.]*|pyw?|pypy[0-9]*w?)\.exe$', re.I)
_MODULE = 'solidworks_mcp.recovery_monitor'


def _absolute_session(value):
    path = Path(value)
    if not path.is_absolute():
        raise RecoveryInventoryUncertain('Worker session path is not absolute')
    return str(path.resolve()).casefold()


def _process_snapshot():
    # WMI exposes command lines for both a venv launcher and its real worker.
    # Missing fields on a Python candidate are UNKNOWN, never evidence of absence.
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    service = rows = None
    try:
        service = win32com.client.GetObject('winmgmts:root/cimv2')
        rows = service.ExecQuery(
            'SELECT ProcessId,Name,ExecutablePath,CommandLine,CreationDate FROM Win32_Process')
        return [dict(pid=int(row.ProcessId), name=row.Name, image=row.ExecutablePath,
                     command_line=row.CommandLine, creation_date=row.CreationDate)
                for row in rows]
    finally:
        # Release WMI interfaces before balancing this thread's COM apartment.
        rows = service = None
        pythoncom.CoUninitialize()


def _creation_microseconds(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{14}\.\d{6}[+-]\d{3}', value):
        raise RecoveryInventoryUncertain('Missing or incomplete WMI process creation time')
    offset = int(value[22:25]) * (1 if value[21] == '+' else -1)
    observed = datetime.strptime(value[:21], '%Y%m%d%H%M%S.%f').replace(
        tzinfo=timezone(timedelta(minutes=offset)))
    delta = observed.astimezone(timezone.utc) - datetime(1601, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _parse_command_line(value):
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    count = ctypes.c_int()
    pointer = shell.CommandLineToArgvW(value, ctypes.byref(count))
    if not pointer:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [pointer[index] for index in range(count.value)]
    finally:
        kernel.LocalFree(pointer)


@contextmanager
def _hold_identity(pid):
    handle = win32api.OpenProcess(win32con.SYNCHRONIZE | 0x1000, False, pid)
    try:
        if win32event.WaitForSingleObject(handle, 0) != win32con.WAIT_TIMEOUT:
            raise RecoveryInventoryUncertain(f'Candidate PID {pid} exited during inventory')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                     wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(int(handle), 0, image, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(int(handle), *(ctypes.byref(value) for value in times)):
            raise ctypes.WinError(ctypes.get_last_error())
        creation = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        import win32process
        yield {'pid': pid, 'image': str(Path(image.value).resolve()),
               'process_start_time': win32process.GetProcessTimes(handle)['CreationTime'].isoformat(),
               'creation_microseconds': creation // 10,
               'is_live': lambda: win32event.WaitForSingleObject(handle, 0) == win32con.WAIT_TIMEOUT}
    finally:
        handle.Close()


def _candidates(rows):
    expected_names = {Path(sys.executable).name.casefold(), Path(sys._base_executable).name.casefold()}
    candidates = {}
    for row in rows:
        name = row.get('name')
        if not isinstance(name, str) or not name:
            raise RecoveryInventoryUncertain('Process inventory has an unknown image name')
        if not (_PYTHON_NAME.fullmatch(name) or name.casefold() in expected_names):
            continue
        pid = row.get('pid')
        if type(pid) is not int or pid <= 0 or pid in candidates:
            raise RecoveryInventoryUncertain('Invalid or duplicate Python PID in inventory')
        if not all(isinstance(row.get(key), str) and row[key] for key in
                   ('image', 'command_line', 'creation_date')):
            raise RecoveryInventoryUncertain(f'Python PID {pid} has unreadable process metadata')
        candidates[pid] = row
    return candidates


def _worker_session(command_line):
    arguments = _parse_command_line(command_line)
    module_positions = [index for index, item in enumerate(arguments) if item == '-m']
    positions = [index for index in module_positions
                 if index + 1 < len(arguments) and arguments[index + 1] == _MODULE]
    if not positions:
        if _MODULE in command_line:
            raise RecoveryInventoryUncertain('Ambiguous recovery worker command line')
        return None
    if len(positions) != 1:
        raise RecoveryInventoryUncertain('Duplicate recovery module arguments')
    tail = arguments[positions[0] + 2:]
    values = []
    for index, item in enumerate(tail):
        if item == '--session-file':
            if index + 1 >= len(tail):
                raise RecoveryInventoryUncertain('Recovery worker is missing its session argument')
            values.append(tail[index + 1])
        elif item.startswith('--session-file='):
            values.append(item.split('=', 1)[1])
    if len(values) != 1:
        raise RecoveryInventoryUncertain('Recovery worker session argument is missing or ambiguous')
    return _absolute_session(values[0])


def observe_session_workers(session_file):
    """Return same-session identities, or raise when absence is not provable.

    No files are modified and no process is launched, controlled or terminated.
    Callers must hold both session mutexes throughout observation and retirement.
    """
    session = _absolute_session(session_file)
    try:
        first = _candidates(_process_snapshot())
        with ExitStack() as held:
            identities = {}
            results = []
            for pid, row in first.items():
                identity = held.enter_context(_hold_identity(pid))
                identities[pid] = identity
                if (str(Path(row['image']).resolve()).casefold() != identity['image'].casefold()
                        or _creation_microseconds(row['creation_date']) != identity['creation_microseconds']):
                    raise RecoveryInventoryUncertain(f'Candidate PID {pid} identity changed during inventory')
                if _worker_session(row['command_line']) == session:
                    results.append({key: identity[key] for key in ('pid', 'image', 'process_start_time')})
                    results[-1].update(command_line=row['command_line'], session_file=session)
            second = _candidates(_process_snapshot())
            if first != second:
                raise RecoveryInventoryUncertain('Python process inventory changed; retry without retiring reservation')
            for pid, identity in identities.items():
                if not identity['is_live']():
                    raise RecoveryInventoryUncertain(f'Candidate PID {pid} exited during inventory')
            return results
    except RecoveryInventoryUncertain:
        raise
    except Exception as exc:
        raise RecoveryInventoryUncertain(f'Recovery process inventory is incomplete: {exc}') from exc
