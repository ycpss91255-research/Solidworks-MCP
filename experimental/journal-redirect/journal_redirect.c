/* Experimental process-local journal routing. Not a supported SW extension. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <wchar.h>
#include <stdio.h>
#include <winternl.h>
#include "MinHook.h"

typedef struct { DWORD owner_pid; WCHAR source[1024]; WCHAR destination[1024]; } JOURNAL_CONFIG;
static WCHAR source_root[1024], destination_root[1024], malformed_source_root[2048];
static DWORD owner;
static HANDLE (WINAPI *original_create)(LPCWSTR,DWORD,DWORD,LPSECURITY_ATTRIBUTES,DWORD,DWORD,HANDLE);
static HANDLE (WINAPI *original_create_a)(LPCSTR,DWORD,DWORD,LPSECURITY_ATTRIBUTES,DWORD,DWORD,HANDLE);
static DWORD (WINAPI *original_attributes)(LPCWSTR);
static BOOL (WINAPI *original_delete)(LPCWSTR);
static BOOL (WINAPI *original_copy)(LPCWSTR,LPCWSTR,BOOL);
static BOOL (WINAPI *original_move)(LPCWSTR,LPCWSTR,DWORD);
static NTSTATUS (NTAPI *original_nt_create)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,PIO_STATUS_BLOCK,PLARGE_INTEGER,ULONG,ULONG,ULONG,ULONG,PVOID,ULONG);

/* -1: target path could not be routed safely; 0: unrelated; 1: redirected. */
static int route(LPCWSTR path, WCHAR *output, size_t capacity) {
    WCHAR full[2048]; WCHAR *name; DWORD length; size_t root_length;
    if (!path || !owner || GetCurrentProcessId()!=owner) return 0;
    /* Observed SW2023 fallback concatenates TEMP with the absolute folder.
       Match only that exact configured folder; never accept arbitrary suffixes. */
    root_length=wcslen(malformed_source_root);
    if(root_length && !_wcsnicmp(path,malformed_source_root,root_length) && path[root_length]==L'\\' &&
       (!_wcsicmp(path+root_length+1,L"swxJRNL.swj") || !_wcsicmp(path+root_length+1,L"swxJRNL.bak"))) {
        name=(WCHAR*)path+root_length+1;
        if(wcslen(destination_root)+wcslen(name)+2>capacity) return -1;
        wcscpy(output,destination_root); wcscat(output,L"\\"); wcscat(output,name); return 1;
    }
    length=GetFullPathNameW(path,2048,full,&name);
    if (!length || length>=2048 || !name) return 0;
    if (_wcsicmp(name,L"swxJRNL.swj") && _wcsicmp(name,L"swxJRNL.bak")) return 0;
    root_length=wcslen(source_root);
    if (_wcsnicmp(full,source_root,root_length) || full[root_length]!=L'\\' ||
        name!=full+root_length+1) return 0;
    if (wcslen(destination_root)+1+wcslen(name)+1>capacity) return -1;
    wcscpy(output,destination_root); wcscat(output,L"\\"); wcscat(output,name);
    return 1;
}

static void record(LPCWSTR operation,LPCWSTR path,DWORD result_error) {
    WCHAR filename[1200],line[2400]; DWORD written; HANDLE file;
    if (!original_create) return;
    _snwprintf(filename,1200,L"%ls\\redirect-events.log",destination_root);
    _snwprintf(line,2400,L"pid=%lu %ls error=%lu %ls\r\n",owner,operation,result_error,path);
    file=original_create(filename,FILE_APPEND_DATA,FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    if (file!=INVALID_HANDLE_VALUE) { WriteFile(file,line,(DWORD)(wcslen(line)*sizeof(WCHAR)),&written,NULL); CloseHandle(file); }
}

static HANDLE WINAPI redirected_create(LPCWSTR path,DWORD access,DWORD sharing,LPSECURITY_ATTRIBUTES security,DWORD disposition,DWORD attributes,HANDLE template_file) {
    WCHAR mapped[2048]; int changed=route(path,mapped,2048); HANDLE result; DWORD error;
    if (changed<0) {SetLastError(ERROR_FILENAME_EXCED_RANGE); return INVALID_HANDLE_VALUE;}
    result=original_create(changed?mapped:path,access,sharing,security,disposition,attributes,template_file);
    if (changed || (path && (wcsstr(path,L"swxJRNL") || wcsstr(path,L"swxjrnl")))) {error=GetLastError(); record(changed?L"CreateFileW ROUTED":L"CreateFileW UNMATCHED",changed?mapped:path,error); SetLastError(error);}
    return result;
}
static HANDLE WINAPI redirected_create_a(LPCSTR path,DWORD access,DWORD sharing,LPSECURITY_ATTRIBUTES security,DWORD disposition,DWORD attributes,HANDLE template_file) {
    WCHAR wide[2048],mapped[2048]; int changed=0; HANDLE result; DWORD error;
    if(path && MultiByteToWideChar(CP_ACP,0,path,-1,wide,2048)) changed=route(wide,mapped,2048);
    else wide[0]=0;
    if(changed<0) {SetLastError(ERROR_FILENAME_EXCED_RANGE); return INVALID_HANDLE_VALUE;}
    result=changed?original_create(mapped,access,sharing,security,disposition,attributes,template_file):original_create_a(path,access,sharing,security,disposition,attributes,template_file);
    if(changed || wcsstr(wide,L"swxJRNL") || wcsstr(wide,L"swxjrnl")) {error=GetLastError(); record(changed?L"CreateFileA ROUTED":L"CreateFileA UNMATCHED",changed?mapped:wide,error); SetLastError(error);}
    return result;
}
static DWORD WINAPI redirected_attributes(LPCWSTR path) {
    WCHAR mapped[2048]; int changed=route(path,mapped,2048);
    if (changed<0) {SetLastError(ERROR_FILENAME_EXCED_RANGE); return INVALID_FILE_ATTRIBUTES;}
    return original_attributes(changed?mapped:path);
}
static NTSTATUS NTAPI redirected_nt_create(PHANDLE handle,ACCESS_MASK access,POBJECT_ATTRIBUTES attributes,PIO_STATUS_BLOCK io,PLARGE_INTEGER size,ULONG file_attributes,ULONG sharing,ULONG disposition,ULONG options,PVOID ea,ULONG ea_length) {
    WCHAR path[2048],mapped[2048],ntpath[2052]; UNICODE_STRING name; OBJECT_ATTRIBUTES local; NTSTATUS status; int changed=0;
    path[0]=0;
    if(attributes && attributes->ObjectName && attributes->ObjectName->Buffer && attributes->ObjectName->Length<sizeof(path)) {
        memcpy(path,attributes->ObjectName->Buffer,attributes->ObjectName->Length);
        path[attributes->ObjectName->Length/sizeof(WCHAR)]=0;
        if(!attributes->RootDirectory && !wcsncmp(path,L"\\??\\",4)) changed=route(path+4,mapped,2048);
    }
    if(changed>0) {
        wcscpy(ntpath,L"\\??\\"); wcscat(ntpath,mapped);
        name.Buffer=ntpath; name.Length=(USHORT)(wcslen(ntpath)*sizeof(WCHAR)); name.MaximumLength=name.Length+sizeof(WCHAR);
        local=*attributes; local.ObjectName=&name; attributes=&local;
    }
    status=original_nt_create(handle,access,attributes,io,size,file_attributes,sharing,disposition,options,ea,ea_length);
    if(changed || wcsstr(path,L"swxJRNL") || wcsstr(path,L"swxjrnl")) {DWORD error=GetLastError(); record(changed?L"NtCreateFile ROUTED":L"NtCreateFile UNMATCHED",changed?mapped:path,(DWORD)status); SetLastError(error);}
    return status;
}
static BOOL WINAPI redirected_delete(LPCWSTR path) {
    WCHAR mapped[2048]; int changed=route(path,mapped,2048);
    if (changed<0) {SetLastError(ERROR_FILENAME_EXCED_RANGE); return FALSE;}
    return original_delete(changed?mapped:path);
}
static BOOL WINAPI redirected_copy(LPCWSTR from,LPCWSTR to,BOOL fail_if_exists) {
    WCHAR a[2048],b[2048]; int x=route(from,a,2048),y=route(to,b,2048);
    if (x<0||y<0) {SetLastError(ERROR_FILENAME_EXCED_RANGE); return FALSE;}
    return original_copy(x?a:from,y?b:to,fail_if_exists);
}
static BOOL WINAPI redirected_move(LPCWSTR from,LPCWSTR to,DWORD flags) {
    WCHAR a[2048],b[2048]; int x=route(from,a,2048),y=route(to,b,2048);
    if (x<0||y<0) {SetLastError(ERROR_FILENAME_EXCED_RANGE); return FALSE;}
    return original_move(x?a:from,y?b:to,flags);
}

__declspec(dllexport) DWORD WINAPI InitializeJournalRedirect(LPVOID data) {
    JOURNAL_CONFIG *config=(JOURNAL_CONFIG*)data; MH_STATUS status; WCHAR temp[1024]; DWORD length;
    if (!config || config->owner_pid!=GetCurrentProcessId() || owner) return 1;
    if (!wmemchr(config->source,0,1024) || !wmemchr(config->destination,0,1024)) return 2;
    if (!config->source[0] || !config->destination[0] ||
        config->source[1]!=L':' || config->destination[1]!=L':' ||
        !_wcsicmp(config->source,config->destination)) return 3;
    wcscpy(source_root,config->source); wcscpy(destination_root,config->destination);
    length=GetTempPathW(1024,temp);
    if(length && length<1024) {
        DWORD expanded=GetLongPathNameW(temp,malformed_source_root,2048);
        if(!expanded || expanded>=2048) wcscpy(malformed_source_root,temp);
    }
    if(length && length<1024 && wcslen(malformed_source_root)+wcslen(source_root)<2048)
        wcscat(malformed_source_root,source_root);
    else malformed_source_root[0]=0;
    owner=config->owner_pid;
    status=MH_Initialize(); if(status!=MH_OK) {owner=0; return 100+status;}
#define INSTALL(name, replacement, original) do { status=MH_CreateHookApi(L"kernel32", name, replacement,(LPVOID*)&original); if(status!=MH_OK) goto failed; } while(0)
    INSTALL("CreateFileW", redirected_create, original_create);
    INSTALL("CreateFileA", redirected_create_a, original_create_a);
    INSTALL("GetFileAttributesW", redirected_attributes, original_attributes);
    INSTALL("DeleteFileW", redirected_delete, original_delete);
    INSTALL("CopyFileW", redirected_copy, original_copy);
    INSTALL("MoveFileExW", redirected_move, original_move);
    status=MH_CreateHookApi(L"ntdll","NtCreateFile",redirected_nt_create,(LPVOID*)&original_nt_create); if(status!=MH_OK) goto failed;
    status=MH_EnableHook(MH_ALL_HOOKS); if(status!=MH_OK) goto failed;
    record(L"INITIALIZED",destination_root,0); record(L"EXACT_FALLBACK_ROOT",malformed_source_root,0); return 0;
failed:
    MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize(); owner=0; return 100+status;
}
__declspec(dllexport) DWORD WINAPI StopJournalRedirect(LPVOID unused) {
    if(owner!=GetCurrentProcessId()) return 1;
    MH_DisableHook(MH_ALL_HOOKS); MH_Uninitialize(); owner=0; return 0;
}
#include "recovery_registry.c"
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    if(reason==DLL_PROCESS_ATTACH) DisableThreadLibraryCalls(module);
    return TRUE;
}
