"""Read-only file-handle evidence for selected Windows 64-bit processes."""
import ctypes as c
from ctypes import wintypes as w
import struct


def journal_handles(pids):
    if c.sizeof(c.c_void_p) != 8:
        raise RuntimeError('Journal handle verification requires Windows 64-bit')
    k = c.WinDLL('kernel32', use_last_error=True)
    n = c.WinDLL('ntdll')
    n.NtQuerySystemInformation.argtypes = [w.ULONG, c.c_void_p, w.ULONG, c.POINTER(w.ULONG)]
    n.NtQuerySystemInformation.restype = c.c_long
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.GetCurrentProcess.restype = w.HANDLE
    k.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
    k.GetFileType.argtypes = [w.HANDLE]
    k.GetFinalPathNameByHandleW.argtypes = [w.HANDLE, w.LPWSTR, w.DWORD, w.DWORD]
    k.CloseHandle.argtypes = [w.HANDLE]
    size = 1024 * 1024
    while True:
        table = c.create_string_buffer(size)
        required = w.ULONG()
        status = n.NtQuerySystemInformation(64, table, size, c.byref(required))
        if status == 0:
            break
        if status not in (-1073741820, -1073741789):  # length mismatch / buffer too small
            raise RuntimeError(f'Cannot query handle table: NTSTATUS {status}')
        size = max(size * 2, required.value + 4096)
        if size > 128 * 1024 * 1024:
            raise RuntimeError('Handle table exceeded verification limit')
    opened = {}
    rows = []
    try:
        for pid in set(pids):
            handle = k.OpenProcess(0x40, False, pid)
            if not handle:
                raise c.WinError(c.get_last_error())
            opened[pid] = handle
        count = struct.unpack_from('Q', table)[0]
        if 16 + count * 40 > size:
            raise RuntimeError('Unexpected handle table layout')
        current = k.GetCurrentProcess()
        path = c.create_unicode_buffer(32768)
        for index in range(count):
            owner, value = struct.unpack_from('QQ', table, 16 + index * 40 + 8)
            if owner not in opened:
                continue
            duplicate = w.HANDLE()
            if not k.DuplicateHandle(opened[owner], value, current, c.byref(duplicate), 0, False, 2):
                continue
            try:
                if k.GetFileType(duplicate) != 1:
                    continue
                length = k.GetFinalPathNameByHandleW(duplicate, path, len(path), 0)
                if 0 < length < len(path) and path.value.lower().endswith('swxjrnl.swj'):
                    rows.append({'pid':owner, 'path':path.value.removeprefix('\\\\?\\')})
            finally:
                k.CloseHandle(duplicate)
    finally:
        for handle in opened.values():
            k.CloseHandle(handle)
    return rows
