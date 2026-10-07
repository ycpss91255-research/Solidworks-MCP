"""Create an interactive process with the existing desktop shell as parent.

The shell's job membership is inherited, so MCP stdio job cleanup cannot
terminate the CAD process. No process handles or MCP pipes are inherited.
"""
import ctypes as c
from ctypes import wintypes as w
import subprocess
import win32api
import win32process


def start_desktop_process(executable, cwd, arguments=()):
    k = c.WinDLL('kernel32', use_last_error=True)
    u = c.WinDLL('user32', use_last_error=True)
    u.GetShellWindow.restype = w.HWND
    u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    shell_pid = w.DWORD()
    shell = u.GetShellWindow()
    if not shell:
        raise RuntimeError('No interactive desktop shell; no process was launched')
    u.GetWindowThreadProcessId(shell, c.byref(shell_pid))
    parent = win32api.OpenProcess(0x1080, False, shell_pid.value)
    try:
        if win32process.GetModuleFileNameEx(parent, 0).split('\\')[-1].lower() != 'explorer.exe':
            raise RuntimeError('Desktop shell is not Explorer; no process was launched')
    except Exception:
        parent.Close()
        raise

    class Startup(c.Structure):
        _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR),
                    ('desktop', w.LPWSTR), ('title', w.LPWSTR),
                    ('x', w.DWORD), ('y', w.DWORD), ('cx', w.DWORD),
                    ('cy', w.DWORD), ('chars_x', w.DWORD), ('chars_y', w.DWORD),
                    ('fill', w.DWORD), ('flags', w.DWORD), ('show', w.WORD),
                    ('reserved_size', w.WORD), ('reserved_data', c.c_void_p),
                    ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]

    class StartupEx(c.Structure):
        _fields_ = [('startup', Startup), ('attributes', c.c_void_p)]

    class ProcessInfo(c.Structure):
        _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE),
                    ('pid', w.DWORD), ('tid', w.DWORD)]

    k.InitializeProcThreadAttributeList.argtypes = [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)]
    k.UpdateProcThreadAttribute.argtypes = [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p,
                                           c.c_size_t, c.c_void_p, c.c_void_p]
    k.DeleteProcThreadAttributeList.argtypes = [c.c_void_p]
    k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p,
                                w.BOOL, w.DWORD, c.c_void_p, w.LPCWSTR,
                                c.POINTER(StartupEx), c.POINTER(ProcessInfo)]
    k.CloseHandle.argtypes = [w.HANDLE]
    size = c.c_size_t()
    k.InitializeProcThreadAttributeList(None, 1, 0, c.byref(size))
    attributes = c.create_string_buffer(size.value)
    initialized = False
    try:
        if not k.InitializeProcThreadAttributeList(attributes, 1, 0, c.byref(size)):
            raise c.WinError(c.get_last_error())
        initialized = True
        parent_handle = w.HANDLE(int(parent))
        if not k.UpdateProcThreadAttribute(attributes, 0, 0x20000,
                                           c.byref(parent_handle), c.sizeof(parent_handle), None, None):
            raise c.WinError(c.get_last_error())
        startup = StartupEx()
        startup.startup.cb = c.sizeof(startup)
        startup.startup.flags = 1  # STARTF_USESHOWWINDOW
        startup.startup.show = 0
        startup.attributes = c.cast(attributes, c.c_void_p)
        info = ProcessInfo()
        command = c.create_unicode_buffer(subprocess.list2cmdline([str(executable), *arguments]))
        if not k.CreateProcessW(str(executable), command, None, None, False,
                                0x80010, None, str(cwd), c.byref(startup), c.byref(info)):
            raise c.WinError(c.get_last_error())
        try:
            return info.pid
        finally:
            k.CloseHandle(info.thread)
            k.CloseHandle(info.process)
    finally:
        if initialized:
            k.DeleteProcThreadAttributeList(attributes)
        parent.Close()
