"""Fresh x64 child only; import prepend adapted from Microsoft Detours uimports.cpp.

Copyright (c) Microsoft Corporation. MIT license, distributed alongside the
experimental native source as Detours-LICENSE.txt. No disk image is modified.
"""
import ctypes as c
from ctypes import wintypes as w
from pathlib import Path
import struct,atexit
from solidworks_mcp.journal_redirect_bootstrap import Config,RecoveryConfig,registry_key_name

class Payload(c.Structure):
    _fields_=[('journal',Config),('recovery',RecoveryConfig),('image',c.c_uint64),
              ('optional_offset',w.DWORD),('original_import',w.DWORD*2),
              ('original_bound',w.DWORD*2),('checksum',w.DWORD),('status',w.DWORD)]
leases=[]
k=c.WinDLL('kernel32',use_last_error=True)
k.CloseHandle.argtypes=[w.HANDLE]
def cleanup():
    for mapping,view in leases:
        k.UnmapViewOfFile.argtypes=[c.c_void_p];k.UnmapViewOfFile(view);k.CloseHandle(mapping)
atexit.register(cleanup)

def preload_created(process,pid,dll,source,destination,recovery=None):
    dll=Path(dll).resolve(strict=True);source=Path(source).resolve(strict=True);destination=Path(destination).resolve()
    if any(len(str(p))>=1024 for p in (source,destination)) or source==destination:raise ValueError('Invalid private paths')
    destination.mkdir(parents=True,exist_ok=True)
    key='';recover=''
    if recovery:
        recover=str(Path(recovery).resolve());Path(recover).mkdir(parents=True,exist_ok=True)
        key=registry_key_name('Software\\SolidWorks\\'+source.name+'\\General')
    nt=c.WinDLL('ntdll')
    nt.NtQueryInformationProcess.argtypes=[w.HANDLE,w.ULONG,c.c_void_p,w.ULONG,c.c_void_p]
    nt.NtQueryInformationProcess.restype=c.c_long
    k.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
    k.WriteProcessMemory.argtypes=k.ReadProcessMemory.argtypes
    k.VirtualAllocEx.argtypes=[w.HANDLE,c.c_void_p,c.c_size_t,w.DWORD,w.DWORD];k.VirtualAllocEx.restype=c.c_void_p
    k.VirtualProtectEx.argtypes=[w.HANDLE,c.c_void_p,c.c_size_t,w.DWORD,c.POINTER(w.DWORD)]
    def read(address,length):
        buffer=c.create_string_buffer(length);done=c.c_size_t()
        if not k.ReadProcessMemory(process,address,buffer,length,c.byref(done)) or done.value!=length:raise c.WinError(c.get_last_error())
        return buffer.raw
    def write(address,data):
        buffer=c.create_string_buffer(data);done=c.c_size_t()
        if not k.WriteProcessMemory(process,address,buffer,len(data),c.byref(done)) or done.value!=len(data):raise c.WinError(c.get_last_error())
    info=c.create_string_buffer(48)
    if nt.NtQueryInformationProcess(process,0,info,48,None)<0:raise RuntimeError('Cannot read fresh process identity')
    peb=struct.unpack_from('<Q',info.raw,8)[0]
    image=struct.unpack('<Q',read(peb+16,8))[0]
    dos=read(image,64)
    if dos[:2]!=b'MZ':raise ValueError('No mapped PE image')
    pe=struct.unpack_from('<I',dos,60)[0]
    header=bytearray(read(image+pe,264))
    if header[:4]!=b'PE\0\0' or struct.unpack_from('<H',header,4)[0]!=0x8664 or struct.unpack_from('<H',header,24)[0]!=0x20b:
        raise ValueError('Only native x64 PE images supported')
    opt=24;import_offset=opt+120;bound_offset=opt+200
    original_import=struct.unpack_from('<II',header,import_offset)
    if not struct.unpack_from('<I',header,opt+208)[0]:
        raise ValueError('Preload requires an existing native IAT directory')
    original_bound=struct.unpack_from('<II',header,bound_offset)
    original_checksum=struct.unpack_from('<I',header,opt+64)[0]
    old_rva,old_size=original_import
    if not old_rva or old_size<20 or old_size>65536:raise ValueError('Unsupported import table')
    old=read(image+old_rva,old_size)
    # Scan descriptor terminator, not potentially padded directory size.
    end=None
    for offset in range(0,len(old)-19,20):
        if old[offset:offset+20]==bytes(20):end=offset+20;break
    if end is None:raise ValueError('Unterminated import table')
    old=old[:end]
    table_offset=(20+len(old)+7)&~7
    name_offset=table_offset+32
    encoded=str(dll).encode('ascii')+b'\0'
    size=name_offset+len(encoded)
    image_size=struct.unpack_from('<I',header,opt+56)[0]
    start=(image+image_size+65535)&~65535
    remote=None
    for address in range(start,min(start+0x20000000,image+0x100000000),65536):
        remote=k.VirtualAllocEx(process,address,size,0x3000,4)
        if remote:break
    if not remote or remote-image+size>0xffffffff:raise RuntimeError('No import arena within image RVA range')
    rva=remote-image
    blob=bytearray(size)
    struct.pack_into('<IIIII',blob,0,rva+table_offset,0,0,rva+name_offset,rva+table_offset+16)
    blob[20:20+len(old)]=old
    struct.pack_into('<QQQQ',blob,table_offset,0x8000000000000001,0,0x8000000000000001,0)
    blob[name_offset:]=encoded
    write(remote,bytes(blob))
    payload=Payload(Config(pid,str(source),str(destination)),RecoveryConfig(pid,key,recover),image,pe+opt,
                    (w.DWORD*2)(*original_import),(w.DWORD*2)(*original_bound),original_checksum,0xffffffff)
    k.CreateFileMappingW.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,w.DWORD,w.DWORD,w.LPCWSTR];k.CreateFileMappingW.restype=w.HANDLE
    k.MapViewOfFile.argtypes=[w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t];k.MapViewOfFile.restype=c.c_void_p
    mapping=k.CreateFileMappingW(c.c_void_p(-1),None,4,0,c.sizeof(payload),f'Local\\SWMCPPreload_{pid}')
    if not mapping:raise c.WinError(c.get_last_error())
    if c.get_last_error()==183:k.CloseHandle(mapping);raise RuntimeError('Fresh process configuration mapping already exists')
    view=k.MapViewOfFile(mapping,6,0,0,c.sizeof(payload))
    if not view:k.CloseHandle(mapping);raise c.WinError(c.get_last_error())
    c.memmove(view,c.byref(payload),c.sizeof(payload));leases.append((mapping,view))
    struct.pack_into('<II',header,import_offset,rva,size)
    struct.pack_into('<II',header,bound_offset,0,0)
    struct.pack_into('<I',header,opt+64,0)
    old_protection=w.DWORD()
    if not k.VirtualProtectEx(process,image+pe,len(header),4,c.byref(old_protection)):raise c.WinError(c.get_last_error())
    try:write(image+pe,bytes(header))
    finally:
        ignored=w.DWORD()
        if not k.VirtualProtectEx(process,image+pe,len(header),old_protection.value,c.byref(ignored)):raise c.WinError(c.get_last_error())
    return view
