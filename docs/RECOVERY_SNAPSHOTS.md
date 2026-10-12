# Explicit part recovery snapshots

`create_recovery_snapshot` creates a native private part copy through an
already-connected, PID-bound MCP. This is the first implemented recovery-copy
operation; it does not restore SolidWorks native AutoRecover or provide a
timer by itself. An opt-in foreground monitor is described below. Assemblies and drawings are deliberately unsupported until their
references can be recovered and verified without saving original components.
External reference files belonging to a part are not packaged by this tool.
The overall journal / recovery goal remains incomplete.

After connecting to this checkout's configured PID:

```json
{"directory":"C:/work/session-a/.codex/recovery"}
```

Pass this object to `create_recovery_snapshot`. The directory must be absolute
and belong to this session. Each process creation identity has its own folder,
and each invocation creates a unique generation containing `part.SLDPRT` and
`manifest.json`. Existing snapshots are retained; nothing is automatically
overwritten or deleted. Restoration is a separate explicit open operation.

The operation checks the configured application PID and holds a process handle.
It fingerprints the saved original file, records its path, title and unsaved
flag, and invokes only SaveAs3 with Silent|Copy (options 3). It checks the source
state and fingerprint afterward and records a complete manifest only when the
save API succeeds, a nonempty copy exists, and the source / PID checks pass.
A failed operation retains a failed manifest and any partial output for
diagnosis; it does not report a recovery copy as successfully completed.

It never calls SaveReferenced, saves the source, reconnects, launches a new CAD
process, takes over another PID, or dismisses dialogs. Connect failure must be
handled according to the workspace's PID isolation rules. No periodic policy
or snapshot root is enabled globally or in another session by this change.
An unsaved new part has no original disk fingerprint. A loaded part whose
original file is missing may also be copied; the tool verifies that it does
not recreate that original path as a side effect.

## Evidence and remaining validation

The underlying copy operation was live-tested on a private SW2023 test PID:
a 5 mm cylinder baseline was changed to 6 mm without saving. SaveAs3 options 3
created a private copy while preserving original path, dirty flag and volume.
The source was closed without saving; reopening the copy through the same
PID-bound MCP recovered one body with volume 1.884955592153876e-6 cubic metres.
The two working SolidWorks instances were left running throughout.

The new tool's guards and MCP schema/dispatch are tested without CAD. A subsequent
actual endpoint test on owned PID 43728 successfully wrote an 82,980-byte native
part snapshot, returned save status zero, and verified identical source path,
title, dirty flag and saved-file SHA256 before/after. Reopening that snapshot
hit a real low-memory warning; its explicitly selected cancel action closed
the warning. The endpoint's own geometry restoration test therefore remains
incomplete. The test instance was empty and exited through its own MCP; the two
working CAD instances retained their identities. Additional required work includes live
scheduler / MCP crash-lifetime integration, assembly/reference recovery,
unsaved-new-document and drawing coverage, and actual native AutoRecover
validation. Do not present this manual part tool as complete automatic recovery.

The prior live test encountered a real low-memory warning on a later reopen;
its explicitly selected cancel action successfully closed that warning. Before
further live tests, inspect current resources and the test PID's actual state.
Do not reopen an already-loaded document or close a working chat's SolidWorks
to make room for a test.

Run the non-CAD checks:

```powershell
python -m unittest tests.test_recovery_snapshot -v
python -m unittest discover -s tests -p 'test_*.py' -q
```

Official API references:
- https://help.solidworks.com/2017/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~SaveAs3.html
- https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swSaveAsOptions_e.html

## Experimental foreground part monitor

The standalone CLI can periodically snapshot a dirty active part in a session's
already-running PID. It requires explicit paths and an explicit interval:

```powershell
python -m solidworks_mcp.recovery_monitor --session-file C:/work/session-a/.codex/solidworks-session.json --directory C:/work/session-a/.codex/recovery --status-file C:/work/session-a/.codex/recovery/monitor.json --interval 60
```

The CLI captures the PID and creation time from that owned session file. It
checks both the live identity and session file on every poll. It never launches
SolidWorks, follows a changed target, or reconnects after a failed bind. A
session-path mutex prevents two monitors for the same session, while allowing
independent sessions. Errors stop the monitor. Its status JSON is restricted
to the private recovery directory and cannot overwrite the CAD session file
or an unrelated status file.

Ticks run sequentially; the next interval starts after the previous save
finishes. Clean parts, missing documents, busy commands, unsupported document
types and visible target-PID dialogs are skipped. Existing dialogs are never
dismissed. Copies remain separate generations, and the monitor never deletes
old backups. `--max-ticks N` bounds an explicit diagnostic run.
`--stop-file <absolute-private-path.stop>` permits an explicit stop request
without terminating CAD. The marker must be inside the private recovery root.
Creating it stops at the next scheduler check; it cannot interrupt a blocked
COM call. An existing stop marker causes immediate stop before connecting.

The CLI can also be started by an opt-in MCP connection hook described below.
It is not enabled in existing chat configurations. Live testing of that hook
and its process/job lifetime with CAD remains pending. A new dialog
or unresponsive CAD process during a COM call can block that call; this initial
CLI does not impose a COM-operation timeout or forcibly close CAD. Keep the
running monitor handle and inspect its worker PID plus creation timestamp
before interpreting an observation timeout as termination. Do not start a
replacement while the previous worker is still live or holds the session lock.

The scheduler, stop/error behavior and status-file boundaries are tested without
CAD. Native Python helper tests verify same-session refusal, independent-session
permission and lock reuse. An expired-target CLI test with inherited automatic
startup enabled verifies that no CAD process is launched. A live SW2023 run on
owned test PID 34340 completed two snapshots 60 seconds apart and stopped at
its explicit two-tick limit. Reopening the second native part copy through
that PID's MCP recovered one body, a 6 mm extrusion, and volume
1.884955592153876e-6 cubic metres. The loaded source retained its unsaved 6 mm
edit; its saved-file SHA256 stayed unchanged. Opening the copy produced no
memory warning. This verifies timed copies and restoration for this standalone
part, not assemblies, drawings, or native AutoRecover. The private native
AutoRecover directory remained empty despite its enabled one-minute setting.
Ignored evidence: `test-results/native-journal/sw-enum-timed-recovery/monitor.json`
and `live-restore-result.json`. This CLI has not been started against either
working SolidWorks or enabled in any chat config.

```powershell
python tests/verify_recovery_monitor_lock_native.py
python tests/verify_recovery_monitor_no_launch.py
python tests/verify_recovery_monitor_lifetime.py
```

The lifetime fixture runs the actual scheduler with a fake backend in a Python
child created through `start_desktop_process`. Closing the parent server's
kill-on-close job did not terminate that child: scheduler ticks continued,
then an explicit stop request caused the worker to exit. This proves the
desktop-parent launch primitive for the scheduler. It does not prove live CAD
snapshots during parent cleanup or implement automatic MCP monitor startup.

## Opt-in MCP connection hook (live integration verification pending)

The `connect_solidworks` endpoint starts or reuses the session's worker only
when these explicitly chosen environment values are supplied:

```text
SOLIDWORKS_RECOVERY_MONITOR=1
SOLIDWORKS_SESSION_FILE=C:/work/session-a/.codex/solidworks-session.json
SOLIDWORKS_RECOVERY_DIRECTORY=C:/work/session-a/.codex/recovery
SOLIDWORKS_RECOVERY_INTERVAL=60
```

The session file must already own the connected PID and its creation time.
The worker uses the desktop-parent launch primitive and persists independently
of MCP's stdio job. It writes `monitor.json` in its private directory before
performing COM operations. Reconnecting MCP checks the worker's live executable
and creation time before reuse. An identity mismatch refuses a duplicate; it
never terminates another process. The worker retains the separate per-session
monitor mutex. A launch mutex serializes connection hooks for that session.

Create `requested.stop` inside that recovery directory to request shutdown.
The hook respects that marker and never removes it automatically. Recovery
startup errors are returned as `recovery_monitor_error` in the connection
details; CAD connection success does not imply recovery is running. Ordinary
implicit CAD connections do not start this hook: explicitly call
`connect_solidworks` after enabling the configuration. This hook remains
experimental until actual MCP restart and live worker lifetime tests pass.

Pack and Go is not yet used as an assembly recovery backend: its official API
documentation describes packaging designated files but does not establish
preservation of unsaved component edits. That behavior requires a real assembly
test with independent source-file and restored-geometry verification.
https://help.solidworks.com/2023/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SavePackAndGo.html
