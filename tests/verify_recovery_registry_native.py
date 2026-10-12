"""Process-local preference fixture; never opens or edits actual SW settings."""
import ctypes as c
from ctypes import wintypes as w
import json,os,subprocess,sys,tempfile,uuid,winreg
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from solidworks_mcp.journal_redirect_bootstrap import Config,RecoveryConfig,registry_key_name
ROOT=Path(__file__).resolve().parents[1]
DLL=Path(os.environ.get('SWMCP_TEST_JOURNAL_DLL',str(ROOT/'test-results/native-journal/journal_redirect.dll')))
if len(sys.argv)>1:
    key,folder=sys.argv[1:]
    root=Path(folder);source=root/'source';private=root/'private';recovery=root/'recover'
    for path in (source,private,recovery):path.mkdir()
    lib=c.WinDLL(str(DLL))
    cfg=Config(os.getpid(),str(source),str(private))
    assert lib.InitializeJournalRedirect(c.byref(cfg))==0
    cfg=RecoveryConfig(os.getpid(),registry_key_name(key),str(recovery))
    wrong=RecoveryConfig(os.getpid()+1,cfg.key,cfg.directory)
    assert lib.InitializeRecoveryRedirect(c.byref(wrong))==1
    assert lib.InitializeRecoveryRedirect(c.byref(cfg))==0
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key,0,winreg.KEY_ALL_ACCESS) as handle:
        assert winreg.QueryValueEx(handle,'AutoRecover Directory')==(str(recovery),winreg.REG_SZ)
        winreg.SetValueEx(handle,'AutoRecover Directory',0,winreg.REG_SZ,str(recovery))
        try:winreg.SetValueEx(handle,'AutoRecover Directory',0,winreg.REG_SZ,'unauthorized')
        except PermissionError:pass
        else:raise AssertionError('Unexpected private preference accepted')
        winreg.SetValueEx(handle,'unrelated',0,winreg.REG_SZ,'normal-write')
        adv=c.WinDLL('advapi32')
        adv.RegQueryValueExW.argtypes=[w.HANDLE,w.LPCWSTR,c.c_void_p,c.POINTER(w.DWORD),c.c_void_p,c.POINTER(w.DWORD)]
        size=w.DWORD();typ=w.DWORD()
        assert adv.RegQueryValueExW(int(handle),'AutoRecover Directory',None,c.byref(typ),None,c.byref(size))==0
        expected=(len(str(recovery))+1)*2
        assert size.value==expected and typ.value==winreg.REG_SZ
        small=c.create_string_buffer(b'guard',5);size=w.DWORD(4)
        assert adv.RegQueryValueExW(int(handle),'AutoRecover Directory',None,c.byref(typ),small,c.byref(size))==234
        assert size.value==expected and small.raw==b'guard'
        adv.RegQueryValueExA.argtypes=[w.HANDLE,w.LPCSTR,c.c_void_p,c.POINTER(w.DWORD),c.c_void_p,c.POINTER(w.DWORD)]
        size=w.DWORD(4096);buffer=c.create_string_buffer(4096)
        assert adv.RegQueryValueExA(int(handle),b'AutoRecover Directory',None,c.byref(typ),buffer,c.byref(size))==0
        assert buffer.value.decode('mbcs')==str(recovery)
        # Prove the native API remains outside the RegQueryValueEx view.
        class Unicode(c.Structure):
            _fields_=[('Length',w.USHORT),('MaximumLength',w.USHORT),('Buffer',w.LPWSTR)]
        text='AutoRecover Directory';name_buffer=c.create_unicode_buffer(text)
        name=Unicode(len(text)*2,(len(text)+1)*2,c.cast(name_buffer,w.LPWSTR))
        nt=c.WinDLL('ntdll')
        nt.NtQueryValueKey.argtypes=[w.HANDLE,c.POINTER(Unicode),w.ULONG,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]
        nt.NtQueryValueKey.restype=c.c_long
        native=c.create_string_buffer(1024);required=w.ULONG()
        assert nt.NtQueryValueKey(int(handle),c.byref(name),2,native,len(native),c.byref(required))==0
        data_length=int.from_bytes(native.raw[8:12],'little')
        original=native.raw[12:12+data_length].decode('utf-16le').rstrip('\0')
        assert original=='parent-original',original
        assert 'NATIVE_QUERY class=2' in (private/'redirect-events.log').read_text(encoding='utf-16le')
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key+'_other',0,winreg.KEY_ALL_ACCESS) as handle:
        assert winreg.QueryValueEx(handle,'AutoRecover Directory')[0]=='other-original'
        winreg.SetValueEx(handle,'AutoRecover Directory',0,winreg.REG_SZ,'other-normal-write')
    assert lib.StopJournalRedirect(None)==0
    print(json.dumps({'private_query':True,'private_write_suppressed':True,'different_directory_rejected':True,'native_query_bypasses_private_view':True}))
else:
    key=r'Software\SWMCPRecoveryFixture_'+uuid.uuid4().hex
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key) as handle:
        winreg.SetValueEx(handle,'AutoRecover Directory',0,winreg.REG_SZ,'parent-original')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key+'_other') as handle:
        winreg.SetValueEx(handle,'AutoRecover Directory',0,winreg.REG_SZ,'other-original')
    try:
        with tempfile.TemporaryDirectory() as folder:
            run=subprocess.run([sys.executable,str(Path(__file__)),key,str(Path(folder).resolve())],capture_output=True,text=True,timeout=20)
            assert run.returncode==0,run.stdout+run.stderr
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as handle:
                assert winreg.QueryValueEx(handle,'AutoRecover Directory')==('parent-original',winreg.REG_SZ)
                assert winreg.QueryValueEx(handle,'unrelated')==('normal-write',winreg.REG_SZ)
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key+'_other') as handle:
                assert winreg.QueryValueEx(handle,'AutoRecover Directory')[0]=='other-normal-write'
            print(json.dumps({'passed':True,'persistent_value_preserved':True,'unrelated_value_normal':True,'solidworks_touched':False}))
    finally:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key+'_other')
