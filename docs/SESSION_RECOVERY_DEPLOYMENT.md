# Session recovery: current result and deployment

## What is implemented

The production launcher uses the installed executable's directory, an Explorer
parent and no inherited MCP stdio handles. It assigns each session its own PID
and creation identity. It does not cap the machine at two instances. A running
target that fails COM attachment is never replaced with another application.

The launcher treats an occupied per-user journal as a nonfatal notice. The
managed connection can dismiss only the exact journal/AutoRecover warning in
its own newly launched PID when `SOLIDWORKS_JOURNAL_WARNING_ACTION=dismiss`.
This does **not** restore native AutoRecover. The production default does not
install the experimental journal-routing DLL or edit shared journal registry
settings. Graphics-path warnings and journal-lock warnings are different;
the earlier graphics warning's exact root cause has not been established.

An independent worker periodically saves private native recovery copies
without saving the source. It persists across MCP exit and reconnect. Every
generation retains a manifest and copies; there is no automatic deletion.
Worker creation, identity changes, unresolved startup and post-start failure
are guarded and reported. See [RECOVERY_SNAPSHOTS.md](RECOVERY_SNAPSHOTS.md) for
the API, implementation checks and chronological test evidence.

## Validated scope and limits

| Case | Real SW2023 evidence |
| --- | --- |
| Dirty standalone saved part | Timed copy and reopened 6 mm cylinder; original disk hash and dirty state preserved |
| New unnamed part | Fresh managed PID 38376; timed copy and reopened 9 mm cylinder |
| Saved assembly with saved component | Endpoint and timed packages; independent copied reference and unsaved 7 mm geometry restored |
| Unsaved assembly placement | Endpoint restored X=0.123 m without changing saved sources |
| Saved two-level nested assembly | Endpoint restored X=0.456 m, child placement X=0.123 m and unsaved 8 mm part with private references |
| Saved single-sheet drawing | Endpoint and timed packages restored an unsaved note and referenced unsaved 8 mm part |
| MCP normal exit and reconnect | Same worker remained live, produced a later copy and was reused |
| Forced MCP termination | Private server job termination after worker startup; worker continued and was reused |

The default monitor protects the **active supported document**, together
with its packaged references. `SOLIDWORKS_RECOVERY_ALL_DOCUMENTS=1` instead scans
open documents and selects dirty supported documents, including clean roots
whose loaded references are dirty. Background part copies need no activation.
Background assembly/drawing packages require the separate explicit setting
`SOLIDWORKS_RECOVERY_BACKGROUND_ACTIVATION=1`: they temporarily activate the
target through API without rebuilding, then restore the previous active
document and its dirty state. This may visibly switch documents within that
session; it never switches another PID. Unexpected external view changes stop
the batch without forcing the user's prior view. A manual
`create_recovery_snapshot` call can also select an
already-open background part through its absolute `filepath`, without opening
or activating it. Background assembly/drawing selection is not supported yet.
The monitor skips commands in progress and visible dialogs; it does
not interrupt a blocked COM call. Part copies do not package external
references. New unsaved assembly/drawing roots are rejected. Mates,
configurations, special component states, advanced drawings and arbitrary
reference dependencies remain unverified. Thus this is a tested private-copy
alternative for the listed cases, not a claim of full native AutoRecover
equivalence or restoration. Native recovery folders in the journal experiments
remained empty despite enabled preferences.

## Per-session setup

### Default: follow the connected SolidWorks preferences

`SOLIDWORKS_RECOVERY_MONITOR` now defaults to `auto` when omitted. On successful
PID-bound MCP attachment it reads that instance's `swAutoSaveEnable` and
`swBackupEnable` preferences without changing them. If both are disabled, no
worker starts. If either is enabled, an owned private worker starts; AutoRecover
minute intervals are converted to seconds. A change-count interval is not
misinterpreted as time: an explicit `SOLIDWORKS_RECOVERY_INTERVAL` is required
for that case. Read failures and missing ownership state return a visible
`recovery_monitor_error`, not a claim that recovery is disabled or protected.

Without a directory override, copies go under
`<session-file-parent>/recovery/<session-file-stem>`. Automatic mode enables
parts, saved assemblies/drawings, all-document scanning and guarded temporary
activation by default, honoring individual explicit scope overrides. It still
has the documented unsupported-reference/root limits. The worker records its
effective options, and the connection reports the native preferences and policy.
Native backup-only mode is an on-save feature; the independent timer supplements
it with unsaved recovery copies using the retained native minute interval or
60 seconds when none is usable. It does not replace native on-save backup
copies, mirror their retention settings, or delete old recovery generations.

Explicit `SOLIDWORKS_RECOVERY_MONITOR=0` disables the independent worker startup
and `1` retains the previous forced opt-in configuration. Worker self-connection
cannot recursively start workers. Settings are read at connection, not watched
continuously: live worker option changes still require the documented owned
stop/restart procedure. In particular, disabling startup does not stop an
already-running worker. The CLI launcher/verifier does not start backup workers;
the owning MCP does after attachment.

Real existing-session validation found AutoRecover enabled with a one-minute
interval and native backup disabled in both MR12 PID 24056 and rack PID 26356.
Connections with no monitor/directory options launched separate workers and
matching reconnects reused them. No CAD application was restarted or launched.
The rack worker completed private snapshots. The first MR12 worker failed on
an assembly package containing references outside the supported part/assembly
types; automatic startup does not establish complete protection for that model.
Package errors now identify the root and unsupported reference paths. They
remain errors, rather than silently omitting dependencies from a claimed
complete recovery package. Reading the currently active MR12 subassembly's
package found only supported paths; that narrower observation does not clear
the failure affecting another root in the all-document batch.
Ignored evidence: `test-results/auto-policy-live-result.json`; inspect each
worker's current `monitor.json` for actual snapshot progress, not just startup.
The 142-test suite covers enabled/disabled preferences, backup-only mode, PID
mismatch, COM read failure, invalid interval modes and explicit overrides.

### MR12 recovery work in progress

The detailed failure identified three STEP dependencies (`SWR12.5-15.stp`,
`VUF10-20.stp`, `JNPN10.stp`). The package backend now accepts `.stp`/`.step`
dependencies and requires each private STEP copy's SHA256 to match its saved
source. Dirty loaded STEP documents are rejected rather than claiming that an
unchanged saved baseline recovers their edits. Missing dependencies and other
unsupported file types remain visible failures.

A subsequent real MR12 attempt reached destination assignment and failed on
incomplete/colliding destinations. NativePack now assigns each source its own
private filename in source order, with a stable path-derived suffix for
duplicate basenames, instead of a global folder override. The native API accepts
a typed BSTR SAFEARRAY; readback must retain every requested destination. A real
read-only rack probe assigned three destinations without saving any file or
changing its active source state. See the official
[SetSaveToName override behavior](https://help.solidworks.com/2021/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IPackAndGo~SetSaveToName.html)
and [per-document assignment contract](https://help.solidworks.com/2021/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ipackandgo~setdocumentsavetonames.html).

The non-CAD suite passes 149 tests. A later owned MR12 worker ended with a COM
object-disconnection error; the cause is not established and no replacement CAD
application was launched. A successful complete MR12 STEP-containing backup
and isolated restore are still pending. The user's authorization for a new
restore-only test instance has been requested; do not interpret passing unit
tests or a filename-assignment probe as proof of complete MR12 recovery.

The monitor and failed batch now retain exception tracebacks to distinguish an
application attachment failure from an invalidated document/reference during
enumeration or copying. Later read-only verification resolved PID 24056 again,
with 35 open documents, but the previously failing generic-robot root was no
longer loaded. Its current worker was live and `waiting_clean`, not producing
another snapshot because it found no dirty supported document. These observations
do not prove the earlier disconnection's cause or successful MR12 recovery.
The rack worker continued producing snapshots (22 confirmed at that check).

### Isolated full-model investigation (not yet a passed recovery test)

The user subsequently authorized isolated testing without repeated permission
questions. A fresh guarded test PID 38376 used its own creation identity and
session file; the two working configurations were not retargeted. The full MR12
source was opened read-only. Its initial dataset contained 2,853 components and
1,402 source files, including three STEP dependencies.

Real probes rejected both BSTR and VARIANT per-document naming arrays, including
identity assignments. The implementation now uses the native folder override
with `FlattenToSingleFolder=False`, which returned unique private destinations.
An existing NTFS short directory alias is used when available, without changing
Windows settings. A short `r-` filename prefix avoids the three outputs that
exceeded MAX_PATH under the former ten-character prefix. SW2023 returned 1,399
zero save codes for the mixed 1,402-file package; complete file presence and
byte-identical STEP copies remain mandatory, independently of that count.

The original pre-save validation rebuilt all source path keys for every output,
causing almost two million resolutions for this model. Source keys are now
computed once and output parent resolutions cached, retaining canonical escape,
collision and source-overwrite checks. The complete suite passes 153 tests.

Later full copies produced all 1,405 files, but the formal root's disk hash
changed during copying and the source-consistency guard rejected them. These
generations remain failed artifacts; none was promoted to a valid recovery.
One was used solely as a detached test fixture. Opening it revealed that two
3D Interconnect links still referred to original STEP locations. Closed-file
dependency inspection with search disabled also found an old D: reference;
search-enabled inspection had hidden it by resolving to a private copy.
`ReplaceReferencedDocument` returned false for these STEP links. Consequently
STEP packages now fail explicitly if their recorded links remain outside the
private generation, rather than claiming that copied STEP bytes alone prove
self-contained recovery.

A pywin32 imported-feature output-parameter probe then produced RPC failure and
test PID 38376 exited. Application event 1000 records that PID (0x95e8) at
21:33 on 2026-10-12, first in `slduiu.dll` (c0000005), then `ntdll.dll`
(c0000374). CAD probing was stopped. The older rack PID 26356 (0x66f4) had a
separate d3d11.dll crash at 21:19, before that imported-feature probe, and its
session state later recorded PID 19780. This timing distinguishes the events
but does not rule out indirect resource effects of loading the full test model.
No test process was deliberately terminated and no other PID was controlled.
Do not repeat the unsafe output-parameter probe; further CAD tests must use a
properly marshaled interface and avoid unsupported feature types.

Ignored investigation evidence is under `test-results/mr12-isolated-proof/`:
source geometry, failed generation manifests, naming probes, recorded STEP
dependencies, detached-fixture linkage inspection and tool outputs. Complete
MR12 automatic backup and isolated restoration remain unverified.

Use an independent checkout/worktree with an absolute session file and private
log and recovery directories. Keep the PID of another chat out of this config.
The MCP command must point to this fork's `solidworks_mcp_server.py` and its
Python environment. The following values explicitly force recovery rather than
following the native enable preference:

```text
SOLIDWORKS_RECOVERY_MONITOR=1
SOLIDWORKS_SESSION_FILE=C:/work/session-a/.codex/solidworks-session.json
SOLIDWORKS_RECOVERY_DIRECTORY=C:/work/session-a/.codex/recovery
SOLIDWORKS_RECOVERY_INTERVAL=60
SOLIDWORKS_RECOVERY_ASSEMBLIES=1
SOLIDWORKS_RECOVERY_DRAWINGS=1
SOLIDWORKS_RECOVERY_ALL_DOCUMENTS=1
SOLIDWORKS_RECOVERY_BACKGROUND_ACTIVATION=1
SOLIDWORKS_JOURNAL_WARNING_ACTION=dismiss
```

For an existing explicitly chosen PID, supply `SOLIDWORKS_TARGET_PID` and keep
automatic launch off. For a user-requested new managed instance, enable
`SOLIDWORKS_AUTO_LAUNCH=1` with this session's own absolute state file; avoid a
seed PID belonging to another chat. Reload/restart the MCP connection after
configuration changes. A file edit alone does not prove the running host used
the new settings.

A persistent worker also records its effective recovery options. Reconnect
rejects a live worker with different or missing settings instead of claiming
the new options took effect or creating a duplicate. To change recovery
options, stop that owned worker, verify its original process handle exited,
explicitly clear its private stop marker, and start the configured replacement.

Connect and check the resolved PID, `session_file`, recovery worker PID and
creation time. Inspect `monitor.json`; reopen a private copy and verify the
expected unsaved geometry/reference before trusting a recovery case. Keep
working CAD process identities and source disk hashes unchanged. A connection
can succeed while returning `recovery_monitor_error`; that does not prove
backup is running.

Create `requested.stop` in the private recovery directory to stop its worker
without closing CAD. A worker startup observation timeout retains an owned
`worker-startup.json` reservation. Inspect the original attempt; do not clear
it or start another worker merely because observation expired.

## Long MCP calls and observation timeouts

The host's `tool_timeout_sec` limits how long a caller waits; it is not evidence
that the SolidWorks COM operation stopped. On 2026-10-12 the rack session's
face/edge/vertex traversal began at 17:28:50.751 and returned success at
17:31:18.401 (147.650 seconds), after the host's 90-second wait had expired.
A subsequent connection resolved the same PID 12616 and later calls succeeded.
This distinguishes that incident from a failed PID attachment. The shared
configuration was not changed or restarted during this diagnosis.

After such a timeout, inspect the original server log and process identity
before retrying a mutation, reconnecting or requesting another instance. Keep
the existing session file and target: a live target must never be replaced
merely because its caller timed out. Split large COM traversals into bounded
read-only calls. If a longer call is required, a per-session host configuration
can use `tool_timeout_sec = 300`, then reload its MCP connection when no call is
pending. The longer wait does not cancel stuck COM operations or establish that
an unfinished operation is safe to repeat. It also does not change the recovery
worker's separate startup/health checks.

## This machine's deployment boundary (2026-10-12)

Before the maintenance window, a read-only audit found the SW2023 `ExtReferences` value
`SolidWorks Journal Folders` set to
`C:\Users\CURRENT_USER\AppData\Roaming\SolidWorks\SOLIDWORKS 2023`, which
does not exist. At that point the production shared path had not been repaired.
The process-local journal experiments and validated private-copy recovery do
not prove this explicit path requirement complete. Correcting a per-user
setting while other working instances may read it has not been validated as
non-interfering; this audit did not write that setting or call their CAD APIs.
The ignored `test-results/native-journal/completion-audit.json` also rechecked
the stored native-copy hashes in the reconnect and final-closure batches.

`repair_journal_path.py` now provides a separate maintenance command. With no
arguments it only inspects the current value, proposed APPDATA-based path and
live CAD PIDs. Explicit `--apply --backup <new-absolute-file>` repairs only the
literal `CURRENT_USER` placeholder, using an exclusive flushed backup before
the registry write and verifying readback. It holds the managed-launch mutex,
refuses any live SolidWorks process, fails closed on process-inventory errors,
and rechecks processes and the registry after preparation. Run it only during
a maintenance window with all CAD closed and no manual launch in progress:
the mutex cannot prevent an external desktop launch between the final check
and write. It records any process observed after writing rather than changing
the setting a second time while that process is starting.

```text
python repair_journal_path.py --version 2023
python repair_journal_path.py --version 2023 --apply --backup C:/work/journal-path-backup.json
```

The real-machine apply probe refused PIDs 9336, 11064 and 12616 before any
registry or backup write. Seven native tests use a disposable registry key to
verify successful repair, live/new-process rejection, inventory and backup
failure, retained external changes and existing-backup protection. The full
suite passes 132 tests. This prepares the path correction without applying it
to working sessions. It neither makes journals independent nor restores native
AutoRecover; those remain distinct from correcting the invalid directory.

### Completed maintenance and post-repair validation

After the user closed all CAD and authorized residual-process closure, the
authoritative inventory was empty. The repair command backed up the original
value and assigned the real APPDATA path, with no process present after writing.
Readback confirmed the directory exists and `CURRENT_USER` is absent. Evidence:
ignored `test-results/journal-path-applied-20261012.json`.

Two new production-launcher sessions then used separate state files. PID 40060
started first with no journal warning event; PID 35176 started second and still
encountered the occupied-journal warning. The exact-PID handler sent its OK
action. Its immediate `closed` observation was false, so that event alone is
not proof of closure. A subsequent exact-PID dialog inventory was clear and
the second instance successfully created a new unnamed 9 mm cylinder.
Thus correcting the bad directory does not eliminate journal contention.

The second session's independent all-document worker produced a native copy
at the configured 60-second interval after its initial MCP exited. A new MCP
resolved the same CAD PID and reused worker 34932. The restore driver initially
failed to unwrap the generated API's `OpenDoc6` tuple; after correcting that
driver, the already-created copy reopened and recovered the expected volume
2.8274333882308137e-6 cubic metres, while the original retained its empty path
and dirty flag. No application replacement or extra CAD launch was used to
recover from that driver error. The first session's creation identity remained
unchanged. Both test applications subsequently exited through their bound APIs,
and the worker's stop marker caused its confirmed exit. Final inventory was
empty and the corrected registry value persisted.

Evidence: ignored `test-results/post-path-{a,b}.{session,connection}.json`,
`post-path-proof/recovery/monitor.json` and `post-path-proof/result.json`.
Together with the earlier seven-document restore and reconnect tests, this
verifies the implemented private-copy alternative within the documented scope.
Native AutoRecover remains un-restored. Recovery options must still be enabled
separately in each intended session; these tests did not enable another chat's
worker or move this chat's host to the prepared worktree.

### Direct automatic-dismissal observation

At the user's request, another production-launcher pair used fresh owned state
files (first PID 33884, second PID 22204). A test observer wrapped the existing
handler's click method without adding another click or close action. It verified
the same PID, exact warning and sole OK button immediately before the production
click. The same HWND became invisible 0.021173 seconds later while still owned
by PID 22204. The production handler subsequently recorded `closed: true`.
This directly proves automatic dismissal in that run, rather than inferring it
from a later empty dialog inventory. It does not prove the warning never appears
or guarantee the same timing in every startup. Both empty owned test instances
were closed through PID-bound MCP and their exits confirmed.

Ignored evidence: `test-results/auto-close-repeat-observation.json`,
`auto-close-repeat-b.connection.json` and `auto-close-repeat-cleanup.json`.

The registered `solidworks-recovery/solidworks_data` worktree has its own config,
state, logs and recovery directory. Its target 38376 was intentionally backed
up and closed at the user's request. Automatic CAD launch is disabled there.
A real stdio MCP loaded that exact TOML, refused the absent PID, and left the
three existing CAD process identities unchanged. Ignored evidence:
`test-results/prepared-config-no-launch-proof.json`.

The all-document MCP integration subsequently passed on the older owned PID
34340: two seven-document batches continued after the first MCP exited;
matching settings reused the same worker while different settings were
rejected. That worker stopped normally. The user then requested closing the
remaining test CAD. Seven fresh native copies preserved its unsaved work,
and its own PID-bound API closed its documents and application. Both owned
test CAD PIDs are now absent; the two working CAD instances were preserved.
See the ignored `all-mcp-reconnect/integration-result.json` and
`final-closure-report.json` under `test-results/native-journal`.

The calling chat still executes in the shared `Downloads/solidworks_data`
checkout. Its session file resolves to the rack chat's PID 12616. That shared
config has not been retargeted or given this test's recovery state. The current
host connection has not switched to the prepared worktree; the worktree tool
does not move the calling chat, and the handoff tool cannot move itself.
Activating that independent execution context and verifying its host MCP is a
remaining deployment step. Do not reopen the intentionally closed CAD merely
to make a connection test pass.

Source changes are pushed only to the fork's `codex/pid-isolation` branch.
Machine-local session state, CAD files and test outputs are not committed.
