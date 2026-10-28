# PID-bound connections and low-memory warning handling

In attach-only mode, start a separate SolidWorks instance, then configure a separate MCP server
with `SOLIDWORKS_TARGET_PID` set to its current process ID. The server binds
only to the exact `SolidWorks_PID_<pid>` Running Object Table entry and verifies
the returned process ID. Missing, invalid, or unavailable targets fail without
launching SolidWorks or connecting to another instance. This variable is
required in attach-only mode: when unset, connection fails before any COM binding or launch.

Set `SOLIDWORKS_MCP_LOG` to a separate log file for each MCP server. The
`{server_pid}` placeholder is expanded to the MCP server process ID so multiple
connections do not write the same log.
For example, an MCP client configuration can use:

```json
{
  "mcpServers": {
    "solidworks-test": {
      "command": "C:/tools/solidworks-mcp/.venv/Scripts/python.exe",
      "args": ["C:/tools/solidworks-mcp/solidworks_mcp_server.py"],
      "env": {
        "SOLIDWORKS_TARGET_PID": "12345",
        "SOLIDWORKS_MCP_LOG": "C:/logs/solidworks-test.log"
      }
    }
  }
}
```

Replace the paths and PID with the actual values. Restart the MCP connection
after changing its environment. Update the PID after restarting SolidWorks.
Install `requirements.txt` in the separate server's Python environment.

## Explicit instance startup

Attach-only MCP never starts SolidWorks. Connection failures must not be bypassed with
shell Start-Process, generic COM Dispatch/DispatchEx, or the old server.
Server initialization instructions and the connection tool description state
this workflow. Shell access is outside MCP's enforcement boundary, so clients
must also follow their workspace AGENTS.md rules.

Use the launcher to verify an existing target:

```powershell
python launch_solidworks.py --pid 12345 --output test-results/session.json
```

Only when a new instance is explicitly requested:

```powershell
python launch_solidworks.py --launch --output test-results/session.json
```

The launcher uses the installed executable's directory as the working
directory, inherits the user's environment, starts hidden, then displays the
new instance after PID-bound COM attachment. It refuses to add an instance
using a required chat-owned session file for duplicate prevention. There is no
machine-wide instance cap. On initialization failure it reports the
new PID and never retries by starting another instance. It does not close
any instance or change journal/AutoRecover settings. Apply the verified PID
and log settings from the manifest to that checkout's MCP configuration,
then restart that MCP connection. Other running connections retain their
startup environment until restarted.

## Opt-in managed automatic startup

To let MCP start SolidWorks when its target has exited, set both variables in
that workspace's MCP environment:

```toml
SOLIDWORKS_AUTO_LAUNCH = '1'
SOLIDWORKS_SESSION_FILE = 'C:\work\project\.codex\solidworks-session.json'
```

Use a distinct absolute session file per independent workspace. Set the tool
timeout to at least 60 seconds (90 seconds recommended for startup). A configured
`SOLIDWORKS_TARGET_PID` seeds the session; after automatic startup the new PID
and process creation time are persisted in the session file, so it does not
require editing the shared config every time SolidWorks restarts. If no seed
PID is supplied, managed mode creates its own instance. Other MCP connections
for the same session file reuse that instance instead of starting duplicates.

Creation uses the same installation-directory launcher, global launch mutex
and per-session duplicate prevention. If the target still exists but COM binding fails, it
reports failure without starting another instance. Access denial, PID reuse,
invalid PID and corrupt session metadata also fail without generic COM fallback.
The session reserves a newly created PID before waiting up to 45 seconds for
COM registration; startup failure keeps that target rather than creating an
alternate instance. MCP does not close existing SolidWorks processes.

Managed mode is explicit authorization for automatic instance creation in that
workspace. Default/global connections remain attach-only unless opted in.
Initial real SolidWorks 2023 managed-start checks connected successfully, but
MCP client cleanup terminated the newly launched CAD child. This was a failed
lifecycle check, not a successful reconnect. The launcher now creates the
process with the existing Explorer desktop shell as parent, using Windows
PROC_THREAD_ATTRIBUTE_PARENT_PROCESS, without inheriting MCP pipes. A native
disposable-process test confirms survival after kill-on-close job cleanup.
Real managed SolidWorks 2023 startup and reconnect subsequently passed: a new
independent instance stayed running after the first stdio client closed, and
a second client reused its recorded PID with launched=false. The pre-existing
MR12 instance remained running and was not accessed through COM.

Instance counts do not prevent journal contention: the first instance
may already hold the per-user swxJRNL.swj file. The launcher now checks existing
default and registry-configured journal files read-only. Windows sharing error
32 is logged as a nonfatal notice and permits independent startup. Other errors,
such as access denied, still stop startup. The earlier refusal on sharing error
was too restrictive and prevented legitimate same-user dual-instance work.
This fixes the launcher blocker, not the shared journal limitation: SolidWorks
may still display its journal/AutoRecover warning. The launcher does not change
shared registry settings or dismiss startup dialogs. An independent process
does not guarantee independent AutoRecover, RAM or per-user preferences.

## Journal isolation experiment (not enabled)

The previously added two-instance cap was removed at the user's request. CLI
launch requires `--session-file` (or a chat-owned `--output`, from which a state
path is derived). Repeated requests reuse that file's live PID, verifying its
creation time, instead of creating another instance. Managed MCP retains its
existing session-file guard. Use a different state file for each independent chat.

`solidworks_mcp/journal_registry.py` provides a reversible registry-folder lease
for the next experiment. It backs up the original value before assigning a
temporary folder, restores after normal or exceptional exit, and refuses to
overwrite a value changed by another program. Existing evidence blocks another
lease until it is inspected. Abrupt process termination still requires explicit
recovery from the backup; this is not automatic crash recovery.

Native tests use only disposable `HKCU/Software/SolidWorksMCPTests` keys.
No actual SolidWorks journal settings were changed by these tests. The module
is available only through an explicitly requested CLI experiment; it is not
enabled by default or in managed MCP startup, and does not establish CAD isolation.
The registry is shared for the Windows user while a lease is active; holding
our launch mutex cannot serialize manual launches or other programs' settings
writes. Other running instances must retain their existing journal handles and
documents throughout a real test. Do not claim no interference without checking.

The real experiment requires a free instance slot. Start only through the
guarded launcher, reserve a unique new folder, observe the new process holding
that folder's journal, restore the original setting, and verify both instances
and MCP reconnects. Inspect startup UI independently of successful COM calls.
Do not use broad silent startup flags or automatic dialog dismissal as proof
that journal creation or AutoRecover works.

Example experiment, only with a free instance slot:

```powershell
python launch_solidworks.py --launch --journal-dir C:/test/new-journal-folder --journal-evidence C:/test/new-journal-lease.json --output C:/test/new-session.json
```

Both journal arguments must be absolute, and the journal directory must be new
or empty. The experiment derives the registry version from the installed exe,
holds the launcher mutex, backs up the value, starts through the normal guarded
launcher and waits up to 45 seconds for the new PID's journal handle. Existing
journal handles must remain present. It restores the value before PID-bound COM
verification. If verification fails after launch, the new PID is kept for
diagnosis; no alternate is launched. Error evidence must be inspected before a
retry. The 45-second registry lease may overlap another program's manual launch
or settings write; this is an experimental limitation, not full registry isolation.

A real SW 2023 probe failed: the new PID did not open the assigned journal in
45 seconds. The original registry value was restored and the existing instance
retained its original journal handle. Thus this technique is not verified as a
working isolation solution and remains experimental.

### Registry lease retest, 2026-10-28: does not work on this install

Retested with direct evidence of the dialog and of the journal handle, same Windows user, three other
SOLIDWORKS sessions holding the shared `swxJRNL.swj`. One fresh chat-owned instance per case, observed for 45 s:

| Case | Warning dialog for the new PID | `swxJRNL.swj` handle of the new PID |
|---|---|---|
| Control (registry untouched) | appeared after 5.7 s, exact text "無法產生日誌檔案。自動復原無法運作…" | none |
| Lease (`SolidWorks Journal Folders` set to a new empty folder for the 45 s window) | **still appeared** after 4.9 s | **none**; the new folder stayed empty |

The value was restored byte-exact (`REG_SZ`, `C:\Users\CURRENT_USER\AppData\Roaming\SolidWorks\SOLIDWORKS 2023`)
and was still original 8 s later; the other sessions' journal handles were unchanged; no other SOLIDWORKS
started during the window. So on this SW 2023 install the value is not honoured for choosing a new instance's
journal: the technique is verified as ineffective here, not merely unverified. Public articles that describe the
value as the journal write location (GoEngineer, CATI) do not apply to this version and setup.

The helper requires absolute paths for the folder and the evidence file as its own safeguard (a relative path
depends on the process working directory); that is not a documented SOLIDWORKS constraint, and the failure is not
caused by path style because the assigned value had no effect at all.

The official Backup/Recover help states that starting a second SOLIDWORKS session produces a message that
auto-recover will not work (linked in `RECOVERY_SNAPSHOTS.md`). With one Windows user there is no verified way to
avoid it. Tested and ineffective: this registry lease, `SetUserPreferenceStringValue(24, ...)`, a child-only
`APPDATA`, and `RegOverridePredefKey`. A separate Windows account was not tested. What remains is the PID-scoped
warning acknowledgement above and, for MCP-driven work, the explicit recovery snapshots in
`RECOVERY_SNAPSHOTS.md`, which do not restore native AutoRecover.

## Explicit journal warning acknowledgement

### Additional real-instance isolation probes

The owned empty SW 2023 instance reported the resolved actual user's roaming
directory through `GetUserPreferenceStringValue(24)`, despite the registry's
`CURRENT_USER` placeholder. This is direct evidence that the placeholder is not,
by itself, the broken path previously inferred from a literal filesystem check.

`SetUserPreferenceStringValue(24, private_folder)` returned true and changed that
instance's API-reported preference. The shared registry value did not change,
and no private journal handle appeared. Calling `RecordLine` with a diagnostic
VBA comment also returned true, but the private `swxJRNL.swj` did not exist and
the instance still had no journal handle. API and registry values were restored;
the pre-existing instance retained its original journal. Successful API return
values are therefore not sufficient proof of journaling or AutoRecover repair.

A separate child-only `APPDATA` experiment was also unsuccessful. The child's
actual environment contained the private roaming directory, but its API still
reported the original user's journal directory, and the journal warning appeared.
It was acknowledged only with the explicitly selected PID-scoped handler. The
original working processes retained their PIDs. The temporary roaming CLI option
was removed after this failed experiment; it is not advertised as a solution.

A disposable-process private-HKCU probe used the documented Windows
`RegOverridePredefKey` API and a temporary test registry subtree. The override
succeeded, but `SHGetFolderPathW(CSIDL_APPDATA)` still returned the real user's
roaming directory instead of the private subtree's AppData setting. This does
not prove SolidWorks startup behavior, but it rules out assuming that a private
registry mapping alone will automatically redirect the Windows profile API.
The actual SolidWorks registry keys and processes were not modified by this
probe. Microsoft documentation states that the override is process-local:
https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regoverridepredefkey

These experiments narrow the remaining issue to actual startup journal routing
or initialization, rather than MCP process selection. Full journal/AutoRecover
isolation remains unverified. Relevant public API documentation:
https://help.solidworks.com/2019/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isldworks~recordline.html

### Acknowledgement configuration and verified limits

For a CLI launch, choose `--journal-warning-action dismiss`. For managed MCP,
set `SOLIDWORKS_JOURNAL_WARNING_ACTION='dismiss'` and restart its connection.
Default is `manual`. Only the session's startup PID is watched; text must match
the specific journal/AutoRecover warning. SW 2023's classic dialog uses native
button ID 2; a task dialog must expose only its known OK button. Process lifetime
and dialog identity are rechecked before the button message, and the result
records closure and errors. It handles one warning, not arbitrary dialogs.

Real SW 2023 verification succeeded for automatic acknowledgement: the dialog
closed, no handler error was recorded, a later MCP connection used the same PID,
and a repeated CLI launch reused the session rather than adding another process.
Both pre-existing working processes remained running. This is acknowledgement
of a warning; the journal and AutoRecover limitation is still present. The popup
can appear briefly before acknowledgement, and AutoRecover is not guaranteed.

Stage 1 was accepted by the user as acknowledgement plus normal independent
session operation; stage 2 continues investigating actual journal/AutoRecover
isolation. A separate real managed-MCP verification also passed: its first
connection launched the owned instance, recorded the journal warning as closed
with no handler errors, and its second independent stdio connection reused the
same PID with launched=false. Both pre-existing process creation identities were
unchanged. The owned test was empty; no production CAD document was accessed.
The user's main workspace, independent MR12 worktree and global MCP defaults
were opted into acknowledgement, without changing their target PIDs. Running
MCP servers must restart to load the new environment. Stage 2 is not complete.

`CURRENT_USER` appears in the default path shown by GoEngineer's journal-warning
documentation. Its literal appearance alone does not prove a configuration
error. This machine's process-handle evidence shows the real journal under the
actual user's roaming directory. The earlier inference of an invalid setting
based only on `Test-Path` was insufficient.

References:
- https://help.solidworks.com/2026/chinese/SolidWorks/sldworks/c_Preventative_File_Management.htm
- https://help.solidworks.com/2019/English/api/swconst/SO_FileLocations.htm
- https://www.goengineer.com/blog/solidworks-warning-journal-file-could-not-be-created

## Low-memory warning during open_document

The optional `memory_warning_action` argument controls this specific warning:

| Value | Behavior |
| --- | --- |
| `manual` (default) | Leave the warning for the user. |
| `continue` | Press Yes and continue opening. |
| `cancel` | Press No and cancel opening. |

```json
{"filepath":"C:/models/example.SLDPRT","memory_warning_action":"continue"}
```

Automatic handling requires `SOLIDWORKS_TARGET_PID`. During `OpenDoc6`, a
watcher identifies visible SOLIDWORKS task dialogs in that process, reads
their text through Windows UI Automation, and verifies both Yes/No buttons.
It recognizes Traditional Chinese, Simplified Chinese, and English low-memory
messages. It posts the documented `TDM_CLICK_BUTTON` message only after
rechecking the target. A held process handle prevents targeting a reused PID.
The watcher handles at most one warning and monitors for up to 30 seconds.
It does not use foreground changes, global keyboard input, or coordinates.

The response includes `memory_warning_events` (including action and whether
closure was observed) and `memory_warning_handler_errors`. Other dialogs are
left untouched. Warnings outside this open operation are not handled. This
does not fix memory shortages or suppress subsequent warnings.

PID binding isolates COM routing, not shared RAM, installation settings, or
per-user journal/AutoRecover resources. Arbitrary `execute_python` code can
still obtain other COM objects; PID binding is not a security sandbox.

## Verification

On Windows with dependencies installed:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/verify_memory_warning_native.py
python tests/verify_no_launch_stdio.py
python tests/verify_desktop_lifetime.py
```

The native test opens disposable helper task dialogs, checks Yes/No return
values and closure, and verifies a separate identical dialog is untouched.
It never attaches to SolidWorks. Output is written under ignored `test-results/`.

Observed validation on SolidWorks 2023 includes PID-bound real MCP connection,
sketch/circle/extrusion, measured solid volume, save/close, reopened file readback,
and reconnect. An actual low-memory warning was recognized read-only; it was
manually dismissed by the user. Automatic dismissal of an actual SolidWorks
warning remains unverified. Native task-dialog tests passed for both actions.
The existing default part-template search also missed a Chinese template;
explicit template selection worked. This change does not fix template search.
