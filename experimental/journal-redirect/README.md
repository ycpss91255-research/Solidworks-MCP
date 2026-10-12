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

Optional `--recovery-private-dir <absolute-new-empty-directory>` adds a
process-local view of the exact current user's SolidWorks General key's
`AutoRecover Directory` value. RegQueryValueExA/W returns the private folder;
RegSetValueExA/W accepts only that exact private assignment without writing
the shared value. A different assignment is denied. All other values and keys
pass through. The bootstrap reads the real HKCU native key identity and passes
it to the new process; no shared registry lease or override is used.

Build instructions remain the same; `recovery_registry.c` must be alongside
`journal_redirect.c`. Verify the optional preference hooks with:

```powershell
python /path/to/checkout/tests/verify_recovery_registry_native.py
```

This fixture checks separate-process persistent-value preservation, unrelated
keys and values, wide/ANSI reads, size-only queries and small buffers. It uses
temporary test registry keys and does not touch SolidWorks settings.

An actual optional-preference test subsequently used a new empty PID 37152.
The API returned the private recovery directory and an explicit assignment
returned true while an independent MCP server read the persistent value as
unchanged. Two independent MCP connections created a baseline part and made
unsaved sketch edits. After 182 seconds from the saved baseline, including a
further edit after the one-minute interval, the private recovery directory
was still empty. AutoRecover remains unverified. The test's documents and
process were then closed via its own MCP; the working PIDs were preserved.

Next investigate startup initialization timing: private directory readback
does not prove that the recovery engine initialized or that its timer is
active. Do not deploy these experiments as a completed recovery fix.

## Early import preload diagnostic

`--journal-preload` selects a separate experimental loader. It prepends the
native routing DLL to the fresh suspended process's in-memory PE import table.
This focused x64 implementation is adapted from Microsoft Detours v4.0.1
`uimports.cpp`; the accompanying MIT license is retained. It supports only
native x64 images with an existing import / IAT directory and an ASCII DLL
path, and fails instead of trying alternate loading methods.

The DLL reads a PID-specific shared-memory configuration during process attach,
validates its PID, installs the hooks, and restores the original import/bound
directory entries and checksum. Its ordinal 1 export is declared explicitly.
Only the newly created process's mapped image is changed. The installed
executable and working processes are untouched. No code-integrity or security
policy is changed. Managed production startup does not enable this loader.

From a folder containing the native source and MinHook source:

```powershell
clang -shared -O2 -static -I./minhook-1.3.4/include preload_wrapper.c preload.def minhook-1.3.4/src/buffer.c minhook-1.3.4/src/hook.c minhook-1.3.4/src/trampoline.c minhook-1.3.4/src/hde/hde64.c -ladvapi32 -o journal_preload.dll
clang -shared -O2 -static constructor_dependency.c '-Wl,--out-implib,constructor_dependency.a' -o constructor_dependency.dll
clang -O2 -static constructor_probe.c constructor_dependency.a -o constructor_probe.exe
```

Put these fixture binaries in the ignored checkout `test-results/native-journal`
folder alongside the ordinary `journal_redirect.dll`, then run:

```powershell
python tests/verify_journal_preload_native.py
```

The fixture opens a fake journal from an imported DLL's process-attach routine.
The old remote-thread bootstrap misses this open; early import preload succeeds
while the parent retains an exclusive original-file lock. It also verifies
restoration of the mapped import directory and the disk executable's hash.
It never launches or connects to SolidWorks.

Windows documents that remote threads wait for DLL initialization:
https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createremotethread .
The import-first technique is documented at
https://github.com/microsoft/Detours/wiki/DetourCreateProcessWithDlls .
These references explain the technique; they do not prove SolidWorks recovery.

The actual early-preload test used PID 6336 with the two original workers left
running. The DLL reported initialization before the application's imports;
the owned instance held a private journal and reported a private recovery
directory. Startup warning events/errors were empty. Independent MCP clients
reconnected to the exact PID. UI inspection showed no blocking dialog.
CommandInProgress was false, UserControl and Visible were true.

After testing unsaved sketches, a one-body cylinder was saved at 5 mm depth,
then changed to 6 mm without saving. MCP measured volume
1.884955592153876e-6 cubic metres and an unsaved flag. After about 291 seconds
from the solid baseline, including a UI rebuild command, the private recovery
directory was still empty. The journal remained zero bytes. The test part and
process were closed through their own MCP, and the two working PID identities
remained unchanged. Early loading alone does not resolve actual AutoRecover.

Existing live session states are reused. Routing/preload options do not
reconfigure an existing instance. Use a new owned state and empty folders for
an explicit new experiment. Recovery engine conditions and a usable recovery
artifact still require investigation; this goal is not complete.

The native journal test uses disposable helper processes and a fake locked journal.
It verifies normal and malformed NT opens, backup operations, owner rejection,
and an unrelated file. It never starts or connects to SolidWorks.

For an explicitly requested live test, use the guarded launcher with absolute
paths and a dedicated, new session state and empty private directory:

```powershell
python launch_solidworks.py --launch --session-file <absolute-own-state.json> --output <absolute-own-connection.json> --journal-redirect-dll <absolute-built-DLL> --journal-source-dir <absolute-actual-journal-directory> --journal-private-dir <absolute-new-private-directory> --journal-warning-action dismiss
```

No compiled DLL is committed. The managed production MCP does not enable this
experiment, and ordinary startup keeps the accepted first-stage behavior.
