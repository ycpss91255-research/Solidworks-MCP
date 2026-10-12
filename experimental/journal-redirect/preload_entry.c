/* Included after the experimental routing DLL source. */
typedef struct {
    JOURNAL_CONFIG journal; RECOVERY_CONFIG recovery; ULONGLONG image;
    DWORD optional_offset; DWORD original_import[2],original_bound[2],checksum,status;
} PRELOAD_PAYLOAD;
static BOOL preload_init(void) {
    WCHAR name[128]; HANDLE mapping; PRELOAD_PAYLOAD *data; DWORD code,protect,ignored; BYTE *optional;
    _snwprintf(name,128,L"Local\\SWMCPPreload_%lu",GetCurrentProcessId());
    mapping=OpenFileMappingW(FILE_MAP_READ|FILE_MAP_WRITE,FALSE,name);
    if(!mapping) return TRUE; /* Ordinary explicit initialization remains available. */
    data=MapViewOfFile(mapping,FILE_MAP_READ|FILE_MAP_WRITE,0,0,sizeof(*data));
    if(!data) {CloseHandle(mapping);return FALSE;}
    code=InitializeJournalRedirect(&data->journal);
    if(!code && data->recovery.directory[0]) code=InitializeRecoveryRedirect(&data->recovery);
    if(!code && data->image==(ULONGLONG)(ULONG_PTR)GetModuleHandleW(NULL)) {
        optional=(BYTE*)(ULONG_PTR)data->image+data->optional_offset;
        if(VirtualProtect(optional,224,PAGE_READWRITE,&protect)) {
            memcpy(optional+120,data->original_import,8);
            memcpy(optional+200,data->original_bound,8);
            memcpy(optional+64,&data->checksum,4);
            if(!VirtualProtect(optional,224,protect,&ignored)) code=901;
        } else code=900;
    } else if(!code) code=902;
    data->status=code;
    if(!code) record(L"PRELOAD_INITIALIZED_BEFORE_IMPORTS",destination_root,0);
    UnmapViewOfFile(data);CloseHandle(mapping);return code==0;
}
