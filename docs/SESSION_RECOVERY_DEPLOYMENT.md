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

The monitor currently protects the **active supported document**, together
with its packaged references. It does not sweep every independently opened
inactive document. A manual `create_recovery_snapshot` call can also select an
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
SOLIDWORKS_JOURNAL_WARNING_ACTION=dismiss
```

For an existing explicitly chosen PID, supply `SOLIDWORKS_TARGET_PID` and keep
automatic launch off. For a user-requested new managed instance, enable
`SOLIDWORKS_AUTO_LAUNCH=1` with this session's own absolute state file; avoid a
seed PID belonging to another chat. Reload/restart the MCP connection after
configuration changes. A file edit alone does not prove the running host used
the new settings.

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

## This machine's deployment boundary (2026-10-12)

The registered `solidworks-recovery/solidworks_data` worktree has its own config,
state, logs and recovery directory. Its target 38376 was intentionally backed
up and closed at the user's request. Automatic CAD launch is disabled there.
A real stdio MCP loaded that exact TOML, refused the absent PID, and left the
three existing CAD process identities unchanged. Ignored evidence:
`test-results/prepared-config-no-launch-proof.json`.

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
