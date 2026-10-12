import ctypes as c,json,os,sys,tempfile,time,struct,hashlib
from ctypes import wintypes as w
from pathlib import Path
import win32api,win32con,win32event,win32file,win32process
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from solidworks_mcp.desktop_process import start_desktop_process
from solidworks_mcp.journal_redirect_bootstrap import initialize_created
from solidworks_mcp.journal_preload_bootstrap import preload_created,Payload
here=root/'test-results/native-journal'
disk_hash=hashlib.sha256((here/'constructor_probe.exe').read_bytes()).hexdigest()
results=[]
with tempfile.TemporaryDirectory() as folder:
    base=Path(folder).resolve();source=base/'source';source.mkdir()
    journal=source/'swxJRNL.swj';journal.write_text('original-protected-journal')
    lock=win32file.CreateFile(str(journal),win32con.GENERIC_READ,0,None,win32con.OPEN_EXISTING,0,None)
    prior=os.environ.get('SWMCP_FAKE_JOURNAL_SOURCE');os.environ['SWMCP_FAKE_JOURNAL_SOURCE']=str(source)
    try:
        for early in (False,True):
            destination=base/('early' if early else 'late');observed=[];views=[]
            def initialize(process,pid):
                observed.append(win32api.OpenProcess(0x100000|0x1000|0x10,False,pid))
                if early:views.append(preload_created(process,pid,here/'journal_preload.dll',source,destination))
                else:initialize_created(process,pid,here/'journal_redirect.dll',source,destination)
            try:
                pid=start_desktop_process(here/'constructor_probe.exe',here,before_resume=initialize)
                if early:
                    deadline=time.monotonic()+10
                    while Payload.from_address(views[0]).status==0xffffffff and time.monotonic()<deadline:time.sleep(0.001)
                    payload=Payload.from_address(views[0])
                    assert payload.status==0,payload.status
                    k=c.WinDLL('kernel32',use_last_error=True)
                    k.ReadProcessMemory.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.c_void_p]
                    buffer=c.create_string_buffer(8)
                    assert k.ReadProcessMemory(int(observed[0]),payload.image+payload.optional_offset+120,buffer,8,None)
                    assert struct.unpack('<II',buffer.raw)==tuple(payload.original_import),'Import directory was not restored'
                assert win32event.WaitForSingleObject(observed[0],15000)==0
                exit_code=win32process.GetExitCodeProcess(observed[0])
                if early:
                    assert Payload.from_address(views[0]).status==0,Payload.from_address(views[0]).status
                    assert exit_code==0,exit_code
                    assert (destination/'swxJRNL.swj').read_text()=='dll-constructor-private-journal'
                else:
                    assert exit_code==1,exit_code
                    assert not (destination/'swxJRNL.swj').exists()
                results.append({'early_import_preload':early,'exit_code':exit_code,'helper_pid':pid})
            finally:
                for process in observed:process.Close()
    finally:
        lock.Close()
        if prior is None:os.environ.pop('SWMCP_FAKE_JOURNAL_SOURCE',None)
        else:os.environ['SWMCP_FAKE_JOURNAL_SOURCE']=prior
    assert journal.read_text()=='original-protected-journal'
assert hashlib.sha256((here/'constructor_probe.exe').read_bytes()).hexdigest()==disk_hash
report={'passed':True,'dll_constructor_requires_early_hook':True,'original_journal_preserved':True,'in_memory_import_directory_restored':True,'on_disk_executable_unchanged':True,'solidworks_touched':False,'cases':results}
(here/'preload-constructor-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
