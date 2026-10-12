#define DllMain ExplicitDllMain
#include "journal_redirect.c"
#undef DllMain
#include "preload_entry.c"
__declspec(dllexport) BOOL RequireRegistryImport(void) {return RegCloseKey(NULL)==ERROR_INVALID_HANDLE;}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
    if(reason==DLL_PROCESS_ATTACH) {DisableThreadLibraryCalls(module);return preload_init();}
    return TRUE;
}
