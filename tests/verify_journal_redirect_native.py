"""Native routing proof using disposable Python children and a locked fake journal."""
import ctypes as c
from ctypes import wintypes as w
import json,os,subprocess,sys,tempfile,struct
from pathlib import Path
import win32con,win32file

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'test-results/native-journal'
DLL=Path(os.environ.get('SWMCP_TEST_JOURNAL_DLL',str(HERE/'journal_redirect.dll'))).resolve(strict=True)
class Config(c.Structure):
    _fields_=[('owner_pid',w.DWORD),('source',w.WCHAR*1024),('destination',w.WCHAR*1024)]

def child(source,destination,wrong=False):
    k=c.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,c.c_void_p,w.DWORD,w.DWORD,w.HANDLE]
    k.CreateFileW.restype=w.HANDLE
    k.WriteFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p]
    k.CloseHandle.argtypes=[w.HANDLE]
    k.MoveFileExW.argtypes=[w.LPCWSTR,w.LPCWSTR,w.DWORD]
    k.CopyFileW.argtypes=[w.LPCWSTR,w.LPCWSTR,w.BOOL]
    k.DeleteFileW.argtypes=[w.LPCWSTR]
    lib=c.WinDLL(str(DLL))
    lib.InitializeJournalRedirect.argtypes=[c.POINTER(Config)]
    lib.InitializeJournalRedirect.restype=w.DWORD
    cfg=Config(os.getpid()+int(wrong),str(source.resolve()),str(destination.resolve()))
    status=lib.InitializeJournalRedirect(c.byref(cfg))
    if wrong:
        assert status==1
        result=k.CreateFileW(str(source/'swxJRNL.swj'),0x40000000,1,None,4,0x80,None)
        assert result==c.c_void_p(-1).value
        print(json.dumps({'wrong_owner_rejected':True,'original_lock_still_effective':True}))
        return
    assert status==0,status
    def write(path,text):
        handle=k.CreateFileW(str(path),0x40000000,1,None,2,0x80,None)
        assert handle!=c.c_void_p(-1).value,c.get_last_error()
        data=text.encode('ascii');done=w.DWORD()
        try:assert k.WriteFile(handle,data,len(data),c.byref(done),None)
        finally:k.CloseHandle(handle)
    try:
        write(source/'swxJRNL.swj','child-private-journal')
        k.GetShortPathNameW.argtypes=[w.LPCWSTR,w.LPWSTR,w.DWORD]
        short=c.create_unicode_buffer(2048)
        assert k.GetShortPathNameW(str(source),short,2048)>0
        for spelling in (short.value+'\\SWXJRNL.SWJ','\\\\?\\'+str(source)+'\\SWXJRNL.SWJ'):
            handle=k.CreateFileW(spelling,0x80000000,3,None,3,0x80,None)
            assert handle!=c.c_void_p(-1).value,(spelling,c.get_last_error())
            k.CloseHandle(handle)
        # Exercise the exact invalid fallback observed in SW2023 through NT.
        class Unicode(c.Structure):
            _fields_=[('Length',w.USHORT),('MaximumLength',w.USHORT),('Buffer',w.LPWSTR)]
        class Attributes(c.Structure):
            _fields_=[('Length',w.ULONG),('RootDirectory',w.HANDLE),('ObjectName',c.POINTER(Unicode)),('Attributes',w.ULONG),('SecurityDescriptor',c.c_void_p),('SecurityQualityOfService',c.c_void_p)]
        class IoStatus(c.Structure):
            _fields_=[('Status',c.c_void_p),('Information',c.c_size_t)]
        nt=c.WinDLL('ntdll')
        nt.NtCreateFile.argtypes=[c.POINTER(w.HANDLE),w.DWORD,c.POINTER(Attributes),c.POINTER(IoStatus),c.c_void_p,w.ULONG,w.ULONG,w.ULONG,w.ULONG,c.c_void_p,w.ULONG]
        nt.NtCreateFile.restype=c.c_long
        invalid='\\??\\'+str(Path(tempfile.gettempdir()).resolve())+'\\'+str(source.resolve())+'\\swxJRNL.swj'
        buffer=c.create_unicode_buffer(invalid)
        name=Unicode(len(invalid)*2,(len(invalid)+1)*2,c.cast(buffer,w.LPWSTR))
        attributes=Attributes(c.sizeof(Attributes),None,c.pointer(name),0x40,None,None)
        handle=w.HANDLE();io=IoStatus()
        status=nt.NtCreateFile(c.byref(handle),0x40000000|0x100000,c.byref(attributes),c.byref(io),None,0x80,3,1,0x20,None,0)
        assert status==0,hex(status&0xffffffff)
        k.CloseHandle(handle)
        valid='\\??\\'+short.value+'\\SWXJRNL.SWJ'
        buffer=c.create_unicode_buffer(valid)
        name=Unicode(len(valid)*2,(len(valid)+1)*2,c.cast(buffer,w.LPWSTR))
        attributes.ObjectName=c.pointer(name)
        nt.NtOpenFile.argtypes=[c.POINTER(w.HANDLE),w.DWORD,c.POINTER(Attributes),c.POINTER(IoStatus),w.ULONG,w.ULONG]
        nt.NtOpenFile.restype=c.c_long
        status=nt.NtOpenFile(c.byref(handle),0x80000000|0x100000,c.byref(attributes),c.byref(io),3,0x20)
        assert status==0,hex(status&0xffffffff)
        k.CloseHandle(handle)
        write(source/'model-control.txt','unrelated-file-in-original-folder')
        assert k.MoveFileExW(str(source/'swxJRNL.swj'),str(source/'swxJRNL.bak'),1)
        assert (destination/'swxJRNL.bak').read_text()=='child-private-journal'
        write(source/'swxJRNL.swj','second-private-journal')
        assert k.CopyFileW(str(source/'swxJRNL.swj'),str(source/'swxJRNL.bak'),False)
        assert (destination/'swxJRNL.bak').read_text()=='second-private-journal'
        assert k.DeleteFileW(str(source/'swxJRNL.bak'))
        # Native rename must never move a private journal into the shared root.
        nt.NtSetInformationFile.argtypes=[w.HANDLE,c.POINTER(IoStatus),c.c_void_p,w.ULONG,w.ULONG]
        nt.NtSetInformationFile.restype=c.c_long
        handle=k.CreateFileW(str(source/'swxJRNL.swj'),0x40000000|0x10000,3,None,3,0x80,None)
        assert handle!=c.c_void_p(-1).value
        try:
            def rename(target):
                encoded=('\\??\\'+str(target)).encode('utf-16le')
                data=bytearray(20+len(encoded));struct.pack_into('<I',data,0,1)
                struct.pack_into('<I',data,16,len(encoded));data[20:]=encoded
                buffer=c.create_string_buffer(bytes(data))
                return nt.NtSetInformationFile(handle,c.byref(io),buffer,len(data),10)
            denied=rename(destination/'..'/'unrelated'/'swxJRNL.bak')
            assert denied&0xffffffff==0xc0000022,hex(denied&0xffffffff)
            assert rename(source/'swxJRNL.bak')==0
        finally:k.CloseHandle(handle)
        assert (destination/'swxJRNL.bak').read_text()=='second-private-journal'
        assert k.MoveFileExW(str(source/'swxJRNL.bak'),str(source/'swxJRNL.swj'),1)
        assert k.DeleteFileW(str(source/'swxJRNL.bak')) or c.get_last_error()==2
        print(json.dumps({'native_open_redirected':True,'short_path_and_uppercase_redirected':True,'extended_prefix_redirected':True,'nt_open_redirected':True,'invalid_nt_fallback_redirected':True,'backup_move_copy_delete_redirected':True,'native_rename_keeps_shared_backup':True,'private_path_escape_denied':True,'unrelated_file_unmodified_routing':True}))
    finally:
        assert lib.StopJournalRedirect(None)==0

if len(sys.argv)>1:
    child(Path(sys.argv[1]),Path(sys.argv[2]),'--wrong-pid' in sys.argv)
else:
    HERE.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        source=Path(folder).resolve()/'source';destination=Path(folder).resolve()/'private'
        source.mkdir();destination.mkdir()
        journal=source/'swxJRNL.swj'; journal.write_text('parent-original-journal')
        backup=source/'swxJRNL.bak';backup.write_text('parent-protected-backup')
        lock=win32file.CreateFile(str(journal),win32con.GENERIC_READ,0,None,win32con.OPEN_EXISTING,0,None)
        results=[]
        try:
            for args in ([],['--wrong-pid']):
                run=subprocess.run([sys.executable,str(Path(__file__)),str(source),str(destination),*args],capture_output=True,text=True,timeout=15)
                if run.returncode:raise RuntimeError(run.stdout+run.stderr)
                results.append(json.loads(run.stdout))
        finally:lock.Close()
        assert journal.read_text()=='parent-original-journal'
        assert (destination/'swxJRNL.swj').read_text()=='second-private-journal'
        assert (source/'model-control.txt').read_text()=='unrelated-file-in-original-folder'
        assert not (destination/'model-control.txt').exists()
        assert backup.read_text()=='parent-protected-backup'
        result={'passed':True,'parent_original_journal_unchanged':True,'cases':results,'solidworks_touched':False}
        (HERE/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
