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
static NTSTATUS (NTAPI *original_nt_open)(PHANDLE,ACCESS_MASK,POBJECT_ATTRIBUTES,PIO_STATUS_BLOCK,ULONG,ULONG);
static NTSTATUS (NTAPI *original_nt_set)(HANDLE,PIO_STATUS_BLOCK,PVOID,ULONG,ULONG);

static BOOL journal_path(LPCWSTR path) {
    LPCWSTR name;
    if(!path) return FALSE;
    name=wcsrchr(path,L'\\');name=name?name+1:path;
    return !_wcsicmp(name,L"swxJRNL.swj") || !_wcsicmp(name,L"swxJRNL.bak");
}

/* -1: target path could not be routed safely; 0: unrelated; 1: redirected. */
static int route(LPCWSTR path, WCHAR *output, size_t capacity) {
    WCHAR full[2048],parent[2048],basename[32]; WCHAR *name; DWORD length; size_t root_length;
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
    if(!wcsncmp(path,L"\\\\?\\",4)) path+=4;
    length=GetFullPathNameW(path,2048,full,&name);
    if (!length || length>=2048 || !name) return 0;
    if (_wcsicmp(name,L"swxJRNL.swj") && _wcsicmp(name,L"swxJRNL.bak")) return 0;
    if(name==full || name[-1]!=L'\\') return 0;
    wcscpy(basename,name);name[-1]=0;
    /* Expand only the existing parent directory, never the locked journal.
       Short-name, mixed-name and extended-prefix spellings must identify the
       same configured folder; other users/folders remain untouched. */
    length=GetLongPathNameW(full,parent,2048);
    if(!length || length>=2048 || _wcsicmp(parent,source_root)) return 0;
    if (wcslen(destination_root)+1+wcslen(basename)+1>capacity) return -1;
    wcscpy(output,destination_root); wcscat(output,L"\\"); wcscat(output,basename);
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
    if (changed || journal_path(path)) {error=GetLastError(); record(changed?L"CreateFileW ROUTED":L"CreateFileW UNMATCHED",changed?mapped:path,error); if(changed)record(L"CreateFileW ORIGINAL",path,error); SetLastError(error);}
    return result;
}
static HANDLE WINAPI redirected_create_a(LPCSTR path,DWORD access,DWORD sharing,LPSECURITY_ATTRIBUTES security,DWORD disposition,DWORD attributes,HANDLE template_file) {
    WCHAR wide[2048],mapped[2048]; int changed=0; HANDLE result; DWORD error;
    if(path && MultiByteToWideChar(CP_ACP,0,path,-1,wide,2048)) changed=route(wide,mapped,2048);
    else wide[0]=0;
    if(changed<0) {SetLastError(ERROR_FILENAME_EXCED_RANGE); return INVALID_HANDLE_VALUE;}
    result=changed?original_create(mapped,access,sharing,security,disposition,attributes,template_file):original_create_a(path,access,sharing,security,disposition,attributes,template_file);
    if(changed || journal_path(wide)) {error=GetLastError(); record(changed?L"CreateFileA ROUTED":L"CreateFileA UNMATCHED",changed?mapped:wide,error); if(changed)record(L"CreateFileA ORIGINAL",wide,error); SetLastError(error);}
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
    if(changed || journal_path(path)) {DWORD error=GetLastError(); record(changed?L"NtCreateFile ROUTED":L"NtCreateFile UNMATCHED",changed?mapped:path,(DWORD)status); if(changed)record(L"NtCreateFile ORIGINAL",path,(DWORD)status); SetLastError(error);}
    return status;
}
static NTSTATUS NTAPI redirected_nt_open(PHANDLE handle,ACCESS_MASK access,POBJECT_ATTRIBUTES attributes,PIO_STATUS_BLOCK io,ULONG sharing,ULONG options) {
    WCHAR path[2048],mapped[2048],ntpath[2052]; UNICODE_STRING name; OBJECT_ATTRIBUTES local; NTSTATUS status; int changed=0;
    path[0]=0;
    if(attributes && attributes->ObjectName && attributes->ObjectName->Buffer && attributes->ObjectName->Length<sizeof(path)) {
        memcpy(path,attributes->ObjectName->Buffer,attributes->ObjectName->Length);
        path[attributes->ObjectName->Length/sizeof(WCHAR)]=0;
        if(!attributes->RootDirectory && !wcsncmp(path,L"\\??\\",4)) changed=route(path+4,mapped,2048);
    }
    if(changed>0) {
        wcscpy(ntpath,L"\\??\\");wcscat(ntpath,mapped);
        name.Buffer=ntpath;name.Length=(USHORT)(wcslen(ntpath)*2);name.MaximumLength=name.Length+2;
        local=*attributes;local.ObjectName=&name;attributes=&local;
    }
    status=original_nt_open(handle,access,attributes,io,sharing,options);
    if(changed || journal_path(path)) {DWORD error=GetLastError();record(changed?L"NtOpenFile ROUTED":L"NtOpenFile UNMATCHED",changed?mapped:path,(DWORD)status);if(changed)record(L"NtOpenFile ORIGINAL",path,(DWORD)status);SetLastError(error);}
    return status;
}
static NTSTATUS NTAPI redirected_nt_set(HANDLE file,PIO_STATUS_BLOCK io,PVOID data,ULONG length,ULONG information_class) {
    WCHAR current[2048],parent[2048],requested[2048],mapped[2048],target[2052],normalized[2048];
    WCHAR *base; DWORD count,error; ULONG name_length,new_length; HANDLE root; BYTE *copy; NTSTATUS status;
    /* FILE_RENAME_INFORMATION and FILE_RENAME_INFORMATION_EX share their
       x64 RootDirectory / FileNameLength / FileName offsets (8 / 16 / 20). */
    if((information_class!=10 && information_class!=65) || !data || length<20 || owner!=GetCurrentProcessId())
        return original_nt_set(file,io,data,length,information_class);
    count=GetFinalPathNameByHandleW(file,current,2048,0);
    if(!count || count>=2048 || !journal_path(current)) return original_nt_set(file,io,data,length,information_class);
    base=!wcsncmp(current,L"\\\\?\\",4)?current+4:current;
    wcscpy(parent,base);
    {
        WCHAR *filename=wcsrchr(parent,L'\\');
        if(!filename)return original_nt_set(file,io,data,length,information_class);
        *filename=0;
        count=GetLongPathNameW(parent,normalized,2048);
        if(!count || count>=2048)return (NTSTATUS)0xC0000022;
    }
    if(_wcsicmp(normalized,destination_root))return original_nt_set(file,io,data,length,information_class);
    count=(DWORD)wcslen(destination_root);
    memcpy(&root,(BYTE*)data+8,sizeof(root));memcpy(&name_length,(BYTE*)data+16,4);
    if(name_length%2 || name_length>=sizeof(requested) || name_length>length-20) return (NTSTATUS)0xC000000D;
    memcpy(requested,(BYTE*)data+20,name_length);requested[name_length/2]=0;
    if(root) {
        count=GetFinalPathNameByHandleW(root,parent,2048,0);
        if(!count || count>=2048) return (NTSTATUS)0xC0000022;
        base=!wcsncmp(parent,L"\\\\?\\",4)?parent+4:parent;
        if(wcslen(base)+wcslen(requested)+2>=2048) return (NTSTATUS)0xC000000D;
        wcscpy(target,base);wcscat(target,L"\\");wcscat(target,requested);
    } else {
        if(!wcschr(requested,L'\\') && journal_path(requested))
            return original_nt_set(file,io,data,length,information_class);
        wcscpy(target,!wcsncmp(requested,L"\\??\\",4)?requested+4:requested);
    }
    count=GetFullPathNameW(target,2048,normalized,NULL);
    if(!count || count>=2048)return (NTSTATUS)0xC000000D;
    wcscpy(target,normalized);
    if(route(target,mapped,2048)<=0) {
        count=(DWORD)wcslen(destination_root);
        if(_wcsnicmp(target,destination_root,count) || target[count]!=L'\\' ||
           wcschr(target+count+1,L'\\') || !journal_path(target)) {
            record(L"NtRename PRIVATE_ESCAPE_DENIED",target,0xC0000022);
            return (NTSTATUS)0xC0000022;
        }
        return original_nt_set(file,io,data,length,information_class);
    }
    wcscpy(target,L"\\??\\");wcscat(target,mapped);
    new_length=(ULONG)(wcslen(target)*2);
    copy=HeapAlloc(GetProcessHeap(),0,20+new_length);
    if(!copy)return (NTSTATUS)0xC0000017;
    memcpy(copy,data,20);root=NULL;memcpy(copy+8,&root,sizeof(root));memcpy(copy+16,&new_length,4);
    memcpy(copy+20,target,new_length);
    status=original_nt_set(file,io,copy,20+new_length,information_class);
    error=GetLastError();record(L"NtRename ROUTED",mapped,(DWORD)status);SetLastError(error);
    HeapFree(GetProcessHeap(),0,copy);return status;
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
    status=MH_CreateHookApi(L"ntdll","NtOpenFile",redirected_nt_open,(LPVOID*)&original_nt_open); if(status!=MH_OK) goto failed;
    status=MH_CreateHookApi(L"ntdll","NtSetInformationFile",redirected_nt_set,(LPVOID*)&original_nt_set); if(status!=MH_OK) goto failed;
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
