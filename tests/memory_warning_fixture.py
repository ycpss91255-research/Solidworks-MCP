"""Independent native Windows task dialog; no SolidWorks/COM attachment."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

folder = Path(sys.argv[1])
manifest = folder / 'taskdialog.manifest'
class ACTCTX(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.ULONG), ('dwFlags', wintypes.DWORD),
                ('lpSource', wintypes.LPCWSTR), ('wProcessorArchitecture', wintypes.USHORT),
                ('wLangId', wintypes.USHORT), ('lpAssemblyDirectory', wintypes.LPCWSTR),
                ('lpResourceName', wintypes.LPCWSTR), ('lpApplicationName', wintypes.LPCWSTR),
                ('hModule', wintypes.HMODULE)]
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.CreateActCtxW.argtypes = [ctypes.POINTER(ACTCTX)]
k.CreateActCtxW.restype = wintypes.HANDLE
k.ActivateActCtx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t)]
ctx = ACTCTX(cbSize=ctypes.sizeof(ACTCTX), lpSource=str(manifest))
handle = k.CreateActCtxW(ctypes.byref(ctx))
assert handle != wintypes.HANDLE(-1).value, ctypes.get_last_error()
cookie = ctypes.c_size_t()
assert k.ActivateActCtx(handle, ctypes.byref(cookie))
comctl = ctypes.WinDLL('comctl32')
comctl.TaskDialog.argtypes = [wintypes.HWND, wintypes.HINSTANCE, wintypes.LPCWSTR,
    wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
selected = ctypes.c_int()
hr = comctl.TaskDialog(None, None, 'SOLIDWORKS', 'TEST ONLY — memory warning fixture',
    'SOLIDWORKS 記憶體嚴重不足 是否要繼續？', 2 | 4, None, ctypes.byref(selected))
assert hr == 0, hr
print(selected.value, flush=True)
