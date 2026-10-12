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
when two or more already exist. On initialization failure it reports the
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
and two-instance limit. If the target still exists but COM binding fails, it
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

The two-instance limit does not prevent journal contention: the first instance
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
