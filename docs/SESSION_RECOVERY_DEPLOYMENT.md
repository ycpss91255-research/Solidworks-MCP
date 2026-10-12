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

An opt-in independent worker periodically saves private native recovery copies
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

Use an independent checkout/worktree with an absolute session file and private
log and recovery directories. Keep the PID of another chat out of this config.
The MCP command must point to this fork's `solidworks_mcp_server.py` and its
Python environment. The following recovery values are opt-in:

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

A read-only completion audit still found the SW2023 `ExtReferences` value
`SolidWorks Journal Folders` set to
`C:\Users\CURRENT_USER\AppData\Roaming\SolidWorks\SOLIDWORKS 2023`, which
does not exist. The production shared path has therefore **not** been repaired.
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
