"""Experimental callback for the freshly created suspended process only."""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import win32process
import winreg
import re

class RecoveryConfig(c.Structure):
    _fields_=[('owner_pid',w.DWORD),('key',w.WCHAR*1024),('directory',w.WCHAR*1024)]

def registry_key_name(subkey):
    """Read the exact native HKCU key identity; never writes the registry."""
    nt=c.WinDLL('ntdll')
    nt.NtQueryKey.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
    nt.NtQueryKey.restype=c.c_long
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,subkey,0,winreg.KEY_QUERY_VALUE) as key:
        buffer=c.create_string_buffer(4096)
        needed=w.ULONG()
        status=nt.NtQueryKey(int(key),3,buffer,len(buffer),c.byref(needed))
        if status<0:raise RuntimeError(f'Native registry key identity failed: {status:#x}')
        length=int.from_bytes(buffer.raw[:4],'little')
        if length>4092 or length%2:raise RuntimeError('Invalid native registry key identity')
        return buffer.raw[4:4+length].decode('utf-16le')

class Config(c.Structure):
    _fields_=[('owner_pid',w.DWORD),('source',w.WCHAR*1024),('destination',w.WCHAR*1024)]

def initialize_created(process,pid,dll,source,destination,recovery_directory=None):
    dll=Path(dll).resolve(strict=True)
    source=Path(source).resolve(strict=True)
    destination=Path(destination).resolve()
    if len(str(source))>=1024 or len(str(destination))>=1024 or source==destination:
        raise ValueError('Invalid experimental journal directories')
    destination.mkdir(parents=True,exist_ok=True)
    k=c.WinDLL('kernel32',use_last_error=True)
    k.VirtualAllocEx.argtypes=[w.HANDLE,c.c_void_p,c.c_size_t,w.DWORD,w.DWORD]
    k.VirtualAllocEx.restype=c.c_void_p
    k.VirtualFreeEx.argtypes=[w.HANDLE,c.c_void_p,c.c_size_t,w.DWORD]
    k.WriteProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
    k.CreateRemoteThread.argtypes=[w.HANDLE,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p,w.DWORD,c.POINTER(w.DWORD)]
    k.CreateRemoteThread.restype=w.HANDLE
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD]
    k.GetExitCodeThread.argtypes=[w.HANDLE,c.POINTER(w.DWORD)]
    k.CloseHandle.argtypes=[w.HANDLE]
    def call(address,data):
        remote=k.VirtualAllocEx(process,None,len(data),0x3000,4)
        if not remote:raise c.WinError(c.get_last_error())
        safe_to_free=True
        try:
            written=c.c_size_t()
            buffer=c.create_string_buffer(data)
            if not k.WriteProcessMemory(process,remote,buffer,len(data),c.byref(written)) or written.value!=len(data):
                raise c.WinError(c.get_last_error())
            thread=k.CreateRemoteThread(process,None,0,address,remote,0,None)
            if not thread:raise c.WinError(c.get_last_error())
            try:
                if k.WaitForSingleObject(thread,30000)!=0:
                    # The caller terminates only its fresh suspended child on
                    # failure. Do not free memory a running remote thread uses.
                    safe_to_free=False
                    raise RuntimeError('New-process journal initialization timed out')
                result=w.DWORD()
                if not k.GetExitCodeThread(thread,c.byref(result)):
                    raise c.WinError(c.get_last_error())
                return result.value
            finally:k.CloseHandle(thread)
        finally:
            if safe_to_free:k.VirtualFreeEx(process,remote,0,0x8000)
    # This callback is never exposed as an attach-by-PID operation. Its caller
    # owns CreateProcess's fresh handle and has not resumed the main thread.
    call(c.cast(k.LoadLibraryW,c.c_void_p).value,(str(dll)+'\0').encode('utf-16le'))
    matches=[]
    for module in win32process.EnumProcessModules(process):
        if Path(win32process.GetModuleFileNameEx(process,module)).resolve()==dll:
            matches.append(int(module))
    if len(matches)!=1:raise RuntimeError('Redirect library was not loaded in the new process')
    local=c.WinDLL(str(dll))  # DllMain installs no hooks; initialization is explicit.
    entry=c.cast(local.InitializeJournalRedirect,c.c_void_p).value-local._handle+matches[0]
    cfg=Config(pid,str(source),str(destination))
    code=call(entry,bytes(cfg))
    if code:raise RuntimeError(f'New-process journal routing initialization failed: {code}')
    if recovery_directory:
        recovery=Path(recovery_directory).resolve()
        if len(str(recovery))>=1024 or not re.fullmatch(r'SOLIDWORKS 20\d\d',source.name,re.IGNORECASE):
            raise ValueError('Invalid experimental recovery directory or SolidWorks version folder')
        recovery.mkdir(parents=True,exist_ok=True)
        key=registry_key_name('Software\\SolidWorks\\'+source.name+'\\General')
        cfg=RecoveryConfig(pid,key,str(recovery))
        entry=c.cast(local.InitializeRecoveryRedirect,c.c_void_p).value-local._handle+matches[0]
        code=call(entry,bytes(cfg))
        if code:raise RuntimeError(f'New-process recovery routing initialization failed: {code}')
