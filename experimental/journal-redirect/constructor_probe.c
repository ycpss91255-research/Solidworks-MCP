#include <windows.h>
__declspec(dllimport) DWORD ConstructorStatus(void);
int main(void) {Sleep(500);return ConstructorStatus()==0?0:1;}
