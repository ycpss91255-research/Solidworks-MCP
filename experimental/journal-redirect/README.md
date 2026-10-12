# Experimental process-local journal routing

This is a diagnostic prototype, disabled by default. It is not a supported
SolidWorks extension and does not establish that AutoRecover works.
It does not alter the installation, shared registry, or existing processes.
The launcher loads it only into the process it has just created, before
resuming that process's main thread. It cannot attach it to an existing PID.
Any bootstrap failure stops only that newly created child.

## Evidence on SolidWorks 2023 SP5

The normal PID-bound startup and explicit journal-warning dismissal are the
accepted first stage. A managed startup and a second MCP connection were
verified to use the same owned PID. No total-instance limit remains.

The routing prototype was tested with two working instances left running.
CreateFileW/A hooks alone did not intercept the journal open. NtCreateFile
diagnostics then observed a malformed fallback path of this form:

```
\??\<expanded user TEMP>\C:\Users\<user>\AppData\Roaming\SolidWorks\SOLIDWORKS 2023\swxJRNL.swj
```

That call returned STATUS_OBJECT_NAME_INVALID (0xC0000033). This identifies
one failing fallback call, not every earlier journal-open attempt. Windows
remote-thread initialization occurs after DLL initialization; this bootstrap
does not intercept every DLL constructor during process startup.

The prototype routes only swxJRNL.swj / swxJRNL.bak at the exact configured
source directory or this exact malformed TEMP-prefixed fallback. The TEMP
directory must be expanded from its short spelling before comparison.
NtCreateFile's OBJECT_ATTRIBUTES are copied; the caller's object is unchanged.
Unrelated paths and other processes retain normal file handling.

Actual test PID 26000 held a private journal while the original working PID
9336 retained its original journal. Startup watcher events/errors were empty,
and independent stdio MCP clients connected to 26000. The test created and
modified its own small part. AutoSaveEnable was true and the interval was one
minute, but AutoSaveDirectory was empty. No recovery file for that part was
found in the inspected TEMP / local SolidWorks trees; one unrelated TEMP
directory denied traversal. The private journal remained zero bytes even
after RecordLine returned true and the owned test exited normally.

Therefore only private journal **open/ownership** and absence of an observed
startup warning passed. Journal contents, usable AutoRecover output, crash
recovery, repeated-launch behavior, and production deployment remain unverified.
All test instances were closed through their own PID-bound MCP after checking
their documents. The two working instance identities were preserved.

## Build and verify

Use the official MinHook v1.3.4 source from
https://github.com/TsudaKageyu/minhook/releases/tag/v1.3.4 . Its release archive
SHA256 is `172708123daa0c98d20d3a980b16a50be14af243dc95dee6f79c24193ad010e4`.
Keep its complete license when distributing a linked binary; a copy is included.
No compiler or dependencies are installed globally by the launcher.

From a folder containing the extracted MinHook source and this C file,
with a Windows x64 LLVM-MinGW clang on PATH:

```powershell
clang -shared -O2 -static -I./minhook-1.3.4/include journal_redirect.c minhook-1.3.4/src/buffer.c minhook-1.3.4/src/hook.c minhook-1.3.4/src/trampoline.c minhook-1.3.4/src/hde/hde64.c -o journal_redirect.dll
$env:SWMCP_TEST_JOURNAL_DLL = (Resolve-Path ./journal_redirect.dll).Path
python /path/to/checkout/tests/verify_journal_redirect_native.py
```

The native test uses disposable helper processes and a fake locked journal.
It verifies normal and malformed NT opens, backup operations, owner rejection,
and an unrelated file. It never starts or connects to SolidWorks.

For an explicitly requested live test, use the guarded launcher with absolute
paths and a dedicated, new session state and empty private directory:

```powershell
python launch_solidworks.py --launch --session-file <absolute-own-state.json> --output <absolute-own-connection.json> --journal-redirect-dll <absolute-built-DLL> --journal-source-dir <absolute-actual-journal-directory> --journal-private-dir <absolute-new-private-directory> --journal-warning-action dismiss
```

No compiled DLL is committed. The managed production MCP does not enable this
experiment, and ordinary startup keeps the accepted first-stage behavior.
