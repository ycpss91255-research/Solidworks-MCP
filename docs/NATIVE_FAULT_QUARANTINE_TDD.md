# Native/RPC fault quarantine — candidate2026-10-15

Status: implementation, mock/protocol regressions and actual owned CN fault-marker
acceptance are verified. This is containment after a fault, not
proof of the first corrupting operation or a completed crash investigation.

## Defect and red/green evidence

The original46576 log continues Save3 after CloseAllDocuments returns
RPC_E_SERVERFAULT, followed by another native heap-corruption event. That ordering
does not prove Save3 first corrupts memory. Inspection also found that MCP only
instructed callers to stop: the next request could still reach the damaged CAD
process. A regression first reproduces this with a synthetic COM server fault:
the following execute_python Save3 request incorrectly succeeds. Four boundary
tests fail before integration, then pass after the guard. Two recovery scheduler
tests separately fail before its integration, then pass.

`native_fault.FaultStore` records PID, process creation identity, signed HRESULT,
message, reporter PID and timestamp under the user's
`~/.solidworks-mcp/native-faults/`. Writes are serialized per PID and replaced
atomically. The first fault for the same identity is retained. Other PIDs and
reused creation identities are independent; this introduces no instance cap.
Ordinary Python/binding errors and RPC call-rejected/busy errors do not create
markers. The guarded HRESULTs are RPC_E_SERVERFAULT, RPC_E_DISCONNECTED,
RPC_S_CALL_FAILED and RPC_S_CALL_FAILED_DNE. They justify stopping automation;
the HRESULT alone is not proof of a particular native corruption mechanism.

MCP dispatch, execute_python, base connection/health probes and new recovery
workers check the marker before invoking CAD. Built-in failures recorded inside
their exception handler and escaping execute_python/worker failures persist
their evidence. Recovery checks precede preference reads, document probes and
saves. If state cannot be verified, the request fails before CAD. Missing creation
identity or a persistence failure is visible and still blocks the observing MCP
process locally; cross-process protection then cannot be claimed.

Two real stdio MCP subprocesses with a fake CAD object verify that an observed
fault blocks the next script and survives server restart. The fake CAD call audit
does not change during blocked requests. This test never binds or starts real CAD.
File-store tests also read a marker from a separate Python interpreter. Production
candidate discovery passes295 tests in12.415s, including these tests; the former273-test
count is historical. The subsequent absolute-resource-gate change passes full298-test
discovery in5.143s. The captured candidate output and source hashes are retained locally
as `native-fault-unit-suite.txt` and `native-fault-candidate-manifest.json`.

The subsequent caught-exception observer integration passes311 tests in8.315s;
actual output is `native-fault-observation-suite.txt`. Its additional real-stdio
test catches the synthetic COM fault inside the script and still verifies an
ERROR response, no later Save3 and persistence across a new MCP process.

Further inspection finds two backup cleanup paths that still invoke CAD after
a native exception: recovery_batch's package activation restoration and
step_recovery's private STEP document close/view restoration. New regressions
first observe four GetProcessID calls instead of the three made before the
fault. They then pass with native failures skipping all remaining verify/close/
activation calls. Ordinary copy/reference failures still restore the original
view and preserve completed snapshots. Explicit SnapshotError cause chains retain
their underlying native HRESULT, and the batch records identity-bound fault
evidence before returning a failed report. These are confirmed failure-handling
defects; they do not prove a backup worker caused an earlier historical crash.
The native replay controls still disable independent recovery monitoring.

## Actual native acceptance and remaining limits

CN's fresh untraced native control reproduces equation51 then fails CloseDoc.
The actual persisted marker matches PID39868/start identity. A fresh automation
object with no app/COM binding is blocked using metadata while the exact faulted
process is still live. Full /ma dump contents/identity/context are validated
before exact-identity cleanup; no CAD call follows the native fault. CO then
connects a fresh different owned PID without inheriting the old quarantine.
See [CN_FULL_DUMP_NATIVE_DISPATCH.md](CN_FULL_DUMP_NATIVE_DISPATCH.md).

When an owned native failure occurs, verify its marker against the actual
session PID/start identity using OS/file-only inspection and a fresh automation
object with no COM binding. Preserve and validate the native dump before retiring
the exact faulted process. Do not test containment by deliberately sending Save3
into that live faulted CAD process. Then verify an owned replacement can connect
without inheriting the old identity's quarantine. Full construction, physical
acceptance and saved/cold acceptance are separate requirements for the mate fix;
fresh uninterrupted CO and separate CP now pass both on the integrated runtime.

This guard operates at request/health/tick boundaries. It cannot interrupt an
already running native call, intercept arbitrary raw COM clients, or protect a
script that catches a native exception and continues raw COM calls inside that
same request. The new exception observer now records even a consumed exception
and prevents a false SUCCESS response on normal script return; later managed
requests/recovery are blocked. It does not sandbox arbitrary Python/COM.
Already-running older MCP/recovery processes do not acquire new code automatically;
they have not been restarted or operated by this investigation. A marker does not
terminate CAD, launch a replacement, save files, clear evidence, change security
settings or dismiss a dialog. Existing managed startup can replace a target only
after its process has exited. Restarting MCP alone does not clear a live identity's
persisted fault marker; do not delete a marker to resume a damaged process.
