# Explicit recovery snapshots

`create_recovery_snapshot` creates a native private part copy through an
already-connected, PID-bound MCP. This is the first implemented recovery-copy
operation; it does not restore SolidWorks native AutoRecover or provide a
timer by itself. An opt-in monitor is described below. The endpoint also offers
an experimental saved assembly/drawing package with saved CAD references.
Missing/unsaved files and non-CAD dependencies are rejected. External reference files
belonging to a part copied through the part backend are not packaged.
The overall journal / recovery goal remains incomplete.

The official Backup/Recover/Version help explicitly states that starting a
second application session produces a message that auto-recover will not work:
https://help.solidworks.com/2026/English/SolidWorks/sldworks/HIDD_OPTIONS_BACKUPS.htm
This is consistent with the SW2023 private test's empty native recovery folder,
but does not prove the exact internal disabling mechanism. Successful private
journal writes and an enabled preference getter do not prove that the native
recovery scheduler is active. The interval mode value 2 means minutes according
to the official `swAutoSaveIntervalMode_e` enumeration; the observed one-minute
setting was not mistakenly a change-count setting.

After connecting to this checkout's configured PID:

```json
{"directory":"C:/work/session-a/.codex/recovery"}
```

Pass this object to `create_recovery_snapshot`. The directory must be absolute
and belong to this session. Each process creation identity has its own folder,
and each invocation creates a unique generation containing `part.SLDPRT` and
`manifest.json`. Existing snapshots are retained; nothing is automatically
overwritten or deleted. Restoration is a separate explicit open operation.

The part operation checks the configured application PID and holds a process handle.
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
MCP crash-lifetime integration, assembly/reference recovery,
unsaved-new-document and advanced drawing coverage, and actual native AutoRecover
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
It is not enabled in existing chat configurations. Its normal MCP exit and
reconnect lifetime has passed a live CAD test described below; forced crash
and kill-on-close job cleanup with live CAD remain unverified. A new dialog
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

## Opt-in MCP connection hook

Each successful PID-bound connection starts or reuses the session's worker only
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
startup errors are returned as `recovery_monitor_error` in connection and CAD
tool responses; CAD connection success does not imply recovery is running.
This hook also runs when a CAD tool connects implicitly. Restart MCP after
enabling the configuration so its automation object loads the new settings.
The recovery worker explicitly disables this connection hook and automatic CAD
launch; its own attach cannot recursively start another worker.

Live SW2023 verification on private PID 34340 passed: the initial MCP connection
launched worker PID 29232; ending that MCP stdio session left the worker alive,
and a second timed snapshot completed after 60 seconds. A new MCP connection
reported `reused: true` with the same worker PID and creation time. The private
stop marker then stopped the worker without closing CAD. Reopening its second
snapshot recovered the unsaved 6 mm extrusion, one body, and the expected volume;
the source stayed dirty and its saved-file SHA256 stayed unchanged. Neither
working CAD PID was controlled. Ignored evidence is in
`test-results/native-journal/sw-enum-mcp-recovery-v2/integration-result.json`
and `live-restore-result.json`. This verifies normal MCP exit/reconnect, not a
forced server crash or live CAD kill-on-close job cleanup.

Windows venv Python can launch a separate base-interpreter process. Startup
confirmation therefore correlates a unique token written by the actual worker
and validates its base executable plus creation time; it does not assume the
CreateProcess launcher PID is the worker PID. The first live attempt exposed
that distinction, returned an explicit startup-observation error, and was
stopped before the corrected test. No replacement was launched on timeout.

Pack and Go is not yet used as an assembly recovery backend: its official API
documentation describes packaging designated files but does not establish
preservation of unsaved component edits. That behavior requires a real assembly
test with independent source-file and restored-geometry verification.

A subsequent private SW2023 assembly probe created a saved one-component
assembly and changed only its private component from 5 to 7 mm without saving.
`IModelDocExtension.GetPackAndGo` returned `DISP_E_PARAMNOTOPTIONAL` through its
generated wrapper and explicit interface dispatch. Its runtime method DISPID
was confirmed as 207; property invocation returned `DISP_E_BADPARAMCOUNT`.
That initial dispatch attempt produced no recovery package. The probe documents remain
loaded in test PID 34340. The separately loaded `ui-baseline.SLDPRT` retained
its unsaved 6 mm edit and unchanged saved-file SHA256. Ignored diagnostic state:
`test-results/native-journal/assembly-recovery-probe/status.json`. Do not enable
assembly monitoring based on this failed probe.

The subsequent native COM vtable probe succeeded. It marshalled the extension
from the existing PID-bound MCP object into the installed type library's
`IModelDocExtension` interface, without another application bind or launch.
`GetPackAndGo` returned the saved assembly and its component. `SavePackAndGo`
returned two zero status codes and created private native copies while retaining
both source files' SHA256 values and unsaved flags. Reopening the packaged
component recovered the unsaved 7 mm extrusion with volume
2.1991148575128554e-6 cubic metres.

A second package used a unique `recovered-` filename prefix. Reopening
`recovered-assembly.SLDASM` through the same PID's MCP loaded one component
whose actual reference path pointed inside that package to
`recovered-component.SLDPRT`; its dimension was 7 mm and its volume matched.
The original assembly and component disk hashes remained unchanged. This
proves a saved, single-component assembly can preserve this unsaved component
edit and recover an independent reference. It does not prove unsaved parent
transforms/mates, nested assemblies, virtual/lightweight/suppressed components,
external references, configurations, or drawings. This original prototype was
followed by the experimental endpoint and timer integration described below.
Ignored evidence: `assembly-recovery-probe/pack-prefix-copy-result.json`
and `assembly-recovery-probe/pack-prefix-restore-result.json` below
`test-results/native-journal`.
https://help.solidworks.com/2023/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SavePackAndGo.html

## Experimental assembly endpoint and timed packages

The existing `create_recovery_snapshot` endpoint now dispatches active saved
assemblies to the native Pack and Go backend. It requires a saved assembly and
saved part or nested assembly reference files; missing/unsaved files and
non-CAD package dependencies are rejected before saving. Each generation has
unique prefixed output filenames. All destinations are checked to be new files
inside the private generation before Pack and Go runs. The manifest records
source file hashes and loaded source paths, titles and dirty flags; any change
prevents a complete result. No fallback source Save or application launch is used.
The installed type library must match the connected CAD's major version.

The new endpoint was live-tested on owned SW2023 PID 34340. Its package reopened
with one reference to its own copied part, preserving the unsaved 7 mm extrusion
and expected volume while leaving source disk hashes unchanged. Ignored evidence:
`assembly-recovery-probe/endpoint-report.json` and `endpoint-restore-result.json`
below `test-results/native-journal`.

Timed assembly copies require a separate explicit opt-in in the worker's
environment (including the launching MCP environment when using the hook):

```text
SOLIDWORKS_RECOVERY_ASSEMBLIES=1
```

The normal default remains part snapshots. With this flag, the monitor checks
both the active assembly's dirty flag and the dirty flags of its loaded
component models. Thus a clean parent with a dirty child requests a snapshot;
that branch has a non-CAD test, not a live clean-parent test yet. The legacy
status marker `part_recovery_monitor` is retained for status-file compatibility.

A bounded live CLI run created two assembly packages 60 seconds apart and exited
at its two-tick limit. The second package reopened through the same PID's MCP
and recovered its own part reference with a 7 mm extrusion and volume
2.1991148575128554e-6 cubic metres. Source assembly and part disk hashes stayed
unchanged. Evidence: `assembly-timed-recovery/monitor.json` and
`assembly-recovery-probe/timed-restore-result.json` under the ignored native test
root. The two working CAD PIDs retained their creation identities and were not
controlled. The assembly option has not been enabled in existing chat configs.

Validation remains incomplete for mates, configurations,
virtual/lightweight/suppressed components, external-reference
semantics and advanced drawing cases. The package API's successful save status does not by
itself prove those cases are recoverable. Native AutoRecover remains unverified;
this is an independent recovery-package mechanism.

## Unsaved transforms and nested assembly verification

A subsequent flat-assembly endpoint test moved its part instance to X=0.123 m
without saving. Reopening the endpoint's package recovered that transform and
the unsaved 7 mm part dimension while preserving source disk hashes. This proves
this direct placement change, not mate edits or every transform/configuration
combination. Evidence: `assembly-recovery-probe/unsaved-transform.json` and
`transform-endpoint-restore-result.json` under the ignored native test root.

The backend now accepts saved nested assembly references. A private two-level
fixture contained a root assembly, one child assembly and one part. The root's
unsaved X translation was 0.456 m; the child's part placement was X=0.123 m,
and the lowest part changed from its saved 7 mm baseline to 8 mm without saving.
The native prototype package and then the actual endpoint package both reopened
with those values and part volume 2.513274122871835e-6 cubic metres. Both levels'
actual reference paths pointed into their own package; all three source file
hashes remained unchanged. This verifies one resolved two-level assembly,
not arbitrary depth, mate/configuration changes or special component states.
Evidence: `nested-recovery-probe/package-result.json`, `restore-result.json`,
`endpoint-report.json` and `endpoint-restore-result.json` below
`test-results/native-journal`. Timed nested restore has not yet been tested;
the prior timer evidence covers the flat assembly. No existing chat config was
changed to enable assembly recovery.

## Experimental drawing packages

The same package backend now accepts a saved drawing as its root, with saved
part and assembly references. The root document type must match its file
extension. Other drawing references and non-CAD dependencies remain rejected.
The endpoint retains the same PID/creation, private-output and source-state
checks. The native backend uses only the extension of the existing PID-bound
COM object; it does not bind a generic application or launch CAD.

Timed drawing copies require `SOLIDWORKS_RECOVERY_DRAWINGS=1` in the worker's
environment. The monitor checks the drawing dirty flag and the loaded models
referenced by its views; for assembly views it also checks loaded component
models. The dirty-model/clean-drawing branch has a non-CAD test. Existing chat
configs were not changed to enable it.

A private SW2023 single-sheet drawing referenced the test part. Its baseline
note was changed to `UNSAVED DRAWING RECOVERY` without saving; the referenced
part also held its unsaved 8 mm edit. Both the native prototype and actual MCP
endpoint package reopened with the new note, a reference to the private copied
part and its 8 mm dimension. The drawing and model source file hashes stayed
unchanged. The fixture's view creation used the actual localized model view
name returned by the API (`*前視`); `*Front` had returned no view on this install.

A bounded live monitor run created two drawing packages 60 seconds apart and
stopped at its explicit two-tick limit. Its second package was reopened and
checked for the same note and private model reference. Evidence is in
`drawing-recovery-probe/package-result.json`, `restore-result.json`,
`endpoint-report.json`, `endpoint-restore-result.json`, `timed-restore-result.json`
and `drawing-timed-recovery/monitor.json` below the ignored native test root.
These tests do not prove multisheet, BOM/table, detached/detailing-mode drawings,
linked external assets, or drawing views of nested assemblies. Native
AutoRecover remains separate from this independent recovery implementation.

## Implicit connection integration

The startup hook now lives in the base PID-bound connection method, so an agent
that directly calls a CAD tool cannot skip the configured recovery startup.
Both attach-only and managed connections pass their actual resolved PID to the
hook only after COM connection success. Connection failure does not start a
worker. Recovery startup failure is recorded and surfaced in subsequent tool
responses rather than reported as a running worker. A connected CAD process
can still be used; the error explicitly means automatic recovery is unavailable.

A fresh MCP on owned SW2023 PID 34340 first called `execute_python` without a
prior `connect_solidworks`. That implicit connection published worker PID 28396.
The explicit connect afterward reported the same worker as reused. Ending that
MCP session left the worker alive; a second drawing snapshot completed after
60 seconds. A second fresh MCP again connected implicitly and reused the same
worker PID and creation time. The private stop marker then stopped the worker.
The recovery backend disabled its own startup hook, avoiding recursive worker
creation despite inheriting the enabled environment. Evidence is in
`sw-implicit-mcp-recovery/integration-result.json` and `monitor.json` below the
ignored native test root. This is a normal MCP-exit test; forced crash/job-close
lifetime remains a separate pending live test. Existing chat configs remain
unchanged.

## Forced MCP server termination

A live SW2023 test forcibly terminated only its newly created MCP server PID
5292 by closing a private Windows job with `KILL_ON_JOB_CLOSE`. The server PID
and creation identity were obtained from that exact MCP connection and checked
before assignment; no CAD PID or other session's MCP was assigned to the job.
Recovery worker PID 30396 remained live and produced a second drawing package
60 seconds later. A fresh MCP connected to the same CAD PID and reused that
same worker PID and creation time. The private stop marker then stopped the
worker. CAD PID 34340 and both working CAD PIDs retained their creation times.
Evidence: `sw-crash-mcp-recovery-v3/integration-result.json` and `monitor.json`
below the ignored native test root.

The job assignment occurred after worker startup. This verifies abrupt MCP
server termination, not worker creation while its parent is already inside that
new job. The earlier native fake-backend lifetime fixture covers that launch
condition indirectly; a live CAD test of that precise condition remains pending.
The first two diagnostic attempts failed before job assignment (result parsing
and the pywin32 unnamed-job argument); their workers stopped via their private
markers, and no CAD process was terminated. No production configuration changed.
