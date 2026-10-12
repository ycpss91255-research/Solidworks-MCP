/* Included in journal_redirect.c; optional, process-local recovery preference. */
typedef struct { DWORD owner_pid; WCHAR key[1024]; WCHAR directory[1024]; } RECOVERY_CONFIG;
static WCHAR recovery_key[1024], recovery_directory[1024];
static NTSTATUS (NTAPI *query_key)(HANDLE,ULONG,PVOID,ULONG,PULONG);
static LSTATUS (WINAPI *real_query_w)(HKEY,LPCWSTR,LPDWORD,LPDWORD,LPBYTE,LPDWORD);
static LSTATUS (WINAPI *real_query_a)(HKEY,LPCSTR,LPDWORD,LPDWORD,LPBYTE,LPDWORD);
static LSTATUS (WINAPI *real_set_w)(HKEY,LPCWSTR,DWORD,DWORD,const BYTE*,DWORD);
static LSTATUS (WINAPI *real_set_a)(HKEY,LPCSTR,DWORD,DWORD,const BYTE*,DWORD);

static BOOL recovery_match(HKEY key,LPCWSTR value) {
    BYTE bytes[4100]; ULONG required; ULONG length;
    if(!recovery_directory[0] || GetCurrentProcessId()!=owner || !value || _wcsicmp(value,L"AutoRecover Directory")) return FALSE;
    if(query_key(key,3,bytes,sizeof(bytes)-2,&required)<0) return FALSE;
    memcpy(&length,bytes,4);
    if(length>sizeof(bytes)-6 || length%2) return FALSE;
    ((WCHAR*)(bytes+4))[length/2]=0;
    return !_wcsicmp((WCHAR*)(bytes+4),recovery_key);
}
static LSTATUS recovery_value(LPDWORD type,LPBYTE data,LPDWORD size,BOOL ansi) {
    DWORD required; CHAR converted[4096]; const void *value=recovery_directory;
    if(!size) return ERROR_INVALID_PARAMETER;
    if(type) *type=REG_SZ;
    if(ansi) {
        required=WideCharToMultiByte(CP_ACP,0,recovery_directory,-1,converted,sizeof(converted),NULL,NULL);
        if(!required) return ERROR_NO_UNICODE_TRANSLATION;
        value=converted;
    } else required=(DWORD)((wcslen(recovery_directory)+1)*sizeof(WCHAR));
    if(data && *size<required) {*size=required; return ERROR_MORE_DATA;}
    if(data) memcpy(data,value,required);
    *size=required; return ERROR_SUCCESS;
}
static LSTATUS WINAPI recovery_query_w(HKEY key,LPCWSTR value,LPDWORD reserved,LPDWORD type,LPBYTE data,LPDWORD size) {
    if(recovery_match(key,value) && !reserved) return recovery_value(type,data,size,FALSE);
    return real_query_w(key,value,reserved,type,data,size);
}
static LSTATUS WINAPI recovery_query_a(HKEY key,LPCSTR value,LPDWORD reserved,LPDWORD type,LPBYTE data,LPDWORD size) {
    if(value && !_stricmp(value,"AutoRecover Directory") && recovery_match(key,L"AutoRecover Directory") && !reserved) return recovery_value(type,data,size,TRUE);
    return real_query_a(key,value,reserved,type,data,size);
}
static LSTATUS WINAPI recovery_set_w(HKEY key,LPCWSTR value,DWORD reserved,DWORD type,const BYTE *data,DWORD size) {
    if(recovery_match(key,value)) {
        /* Only an exact private-directory assignment is accepted. No shared write. */
        DWORD expected=(DWORD)((wcslen(recovery_directory)+1)*2);
        if(reserved || type!=REG_SZ || !data || size!=expected || memcmp(data,recovery_directory,expected)) return ERROR_ACCESS_DENIED;
        record(L"RecoveryPreference PRIVATE_WRITE",recovery_directory,0); return ERROR_SUCCESS;
    }
    return real_set_w(key,value,reserved,type,data,size);
}
static LSTATUS WINAPI recovery_set_a(HKEY key,LPCSTR value,DWORD reserved,DWORD type,const BYTE *data,DWORD size) {
    if(value && !_stricmp(value,"AutoRecover Directory") && recovery_match(key,L"AutoRecover Directory")) {
        CHAR converted[4096]; int expected=WideCharToMultiByte(CP_ACP,0,recovery_directory,-1,converted,sizeof(converted),NULL,NULL);
        if(reserved || type!=REG_SZ || !data || !expected || size!=(DWORD)expected || memcmp(data,converted,expected)) return ERROR_ACCESS_DENIED;
        record(L"RecoveryPreference PRIVATE_WRITE",recovery_directory,0); return ERROR_SUCCESS;
    }
    return real_set_a(key,value,reserved,type,data,size);
}
__declspec(dllexport) DWORD WINAPI InitializeRecoveryRedirect(LPVOID data) {
    RECOVERY_CONFIG *config=(RECOVERY_CONFIG*)data; MH_STATUS status;
    if(!config || owner!=GetCurrentProcessId() || config->owner_pid!=owner || recovery_directory[0]) return 1;
    if(!wmemchr(config->key,0,1024) || !wmemchr(config->directory,0,1024) || !config->key[0] || config->directory[1]!=L':') return 2;
    query_key=(void*)GetProcAddress(GetModuleHandleW(L"ntdll"),"NtQueryKey");
    if(!query_key) return 3;
    wcscpy(recovery_key,config->key); wcscpy(recovery_directory,config->directory);
#define REGHOOK(name, replacement, original) do { status=MH_CreateHookApi(L"advapi32",name,replacement,(LPVOID*)&original); if(status!=MH_OK) goto recovery_failed; } while(0)
    REGHOOK("RegQueryValueExW",recovery_query_w,real_query_w);
    REGHOOK("RegQueryValueExA",recovery_query_a,real_query_a);
    REGHOOK("RegSetValueExW",recovery_set_w,real_set_w);
    REGHOOK("RegSetValueExA",recovery_set_a,real_set_a);
    status=MH_EnableHook(MH_ALL_HOOKS); if(status!=MH_OK) goto recovery_failed;
    record(L"RecoveryPreference INITIALIZED",recovery_directory,0); return 0;
recovery_failed:
    recovery_directory[0]=0; return 100+status;
}
