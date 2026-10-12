#include <windows.h>
#include <stdio.h>
static DWORD status=999;
__declspec(dllexport) DWORD ConstructorStatus(void) {return status;}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    if(reason==DLL_PROCESS_ATTACH) {
        WCHAR folder[1024],path[1200];HANDLE file;DWORD written;
        if(!GetEnvironmentVariableW(L"SWMCP_FAKE_JOURNAL_SOURCE",folder,1024)) return FALSE;
        _snwprintf(path,1200,L"%ls\\swxJRNL.swj",folder);
        file=CreateFileW(path,GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
        status=file==INVALID_HANDLE_VALUE?GetLastError():0;
        if(file!=INVALID_HANDLE_VALUE) {WriteFile(file,"dll-constructor-private-journal",31,&written,NULL);CloseHandle(file);}
        DisableThreadLibraryCalls(module);
    }
    return TRUE;
}
