# Reproduced native mate-edit / CloseDoc failure

Environment: SOLIDWORKS2023SP5 (31.5.0.52), typed pywin32 plus native comtypes
mate-definition access, private copies only. Investigation dated2026-10-14.

Original other-session PID38068: native limit-mate repair reports success;
reopen_verify_ap45_saved_limits.py then returns RPC_E_SERVERFAULT from typed
ISldWorks.CloseDoc (DISPID7). Event1000 at11:41:31 Asia/Taipei records mfc140u.dll
c0000005 offset0x23dc91. A later ntdll heap fault at11:43 follows further CAD
calls to that already faulted process. This investigation did not operate it.

Owned trial O PID35180, pre-repair AP45 and stage3 backup assembly overrides:
the native four-mate loop sets IsAdvancedMate, ranges and Distance on the first
three AP45 mates, ModifyDefinition, rebuild and Save3; the fourth stage3 mate
already has the expected range, so it is queried and saved without conversion.
Subsequent CloseDoc returns RPC_E_SERVERFAULT; event1000 at11:59:16 has exactly
the same mfc140u.dll c0000005 offset0x23dc91. No exporter invocation or backup
worker, no low-memory warning, committed memory about82.7% of limit.

Controls:
- N: current saved-state AP45 rebuild/save/CloseDoc succeeds.
- P: same two pre-repair assembly backups without native mate edits succeed.
- Q/R/S: separately convert only the first, second, or third AP45 mate; all
  edit/save/CloseDoc paths succeed. Frozen230-file private input hashes match
  across these trials and T. This does not reconstruct all original live edits.
- T PID38536: restore identical frozen bytes, run the entire four-mate loop;
  CloseDoc again returns RPC_E_SERVERFAULT. Event1000 at12:11:11 records
  dcu3d59.dll c0000005 offset0x11073, matching multiple Oct13 historical events.

The full native edit/inspection sequence followed by close is a reproducible
trigger. Neither one AP45 mate conversion alone nor the saved-state close alone
is sufficient in these controls. This does NOT yet distinguish combined solver
state, the fourth nested mate inspection/save, retained COM lifetimes, or the
specific COM/native implementation defect. Do not ban all ModifyDefinition or
all CloseDoc, and do not claim every historical fault has one common root cause.

CAD calls stopped after each native fault. Owned live post-fault MiniDumpNormal
files were saved locally (O1,341,083bytes; T1,352,483bytes), without exception
pointers: these are not exception-time full-heap dumps. Held process handles,
executable paths, creation times and preserved input hashes verified before
terminating only those owned faulted test processes. Other sessions untouched.

Evidence remains local in test-results/remaining-fault-correlation: report-o,
report-p/q/r/s/t, trace directories, owned-o/t-capture metadata and dumps,
frozen230-file hashes, and exact adapted scripts. Dumps and CAD data are not
published. Next comparisons: first-three conversions together without fourth
mate inspection, and object-release/typed-vs-native access controls if needed.

Further equal-input comparisons:
- U PID44264: first-three native/comtypes conversions together, omitting the
  fourth nested-document operation, still fail CloseDoc. Event1000 at12:15:03
  is unknown module c0000005 offset0x108. Thus fourth operation is unnecessary;
  native fault location varies across equivalent trigger sequences. Launcher
  also printed an IUnknown release exception before trial; this is recorded as
  an additional possible lifetime confound, not discarded or explained away.
- V PID24416: same frozen230 inputs and first-three conversions, replace only
  native/comtypes definition queries and ModifyDefinition arguments with typed
  pywin32 IFeature/IDistanceMateFeatureData/IModelDoc2 objects. Original range
  assertions, rebuilds, saves and CloseDoc succeed; owned process exits; no
  corresponding event1000. No native_interface/QueryInterface bridge calls.

V is an initial prevention candidate for this mate workflow, not a blanket cure
for COM, the backup marshal bridge, or all CAD operations. Repeat the full
four-mate sequence through typed pywin32 and cold reopen before recommending
the alternative as verified. This does not prove the precise unsafe lifetime
or vendor implementation mechanism in the failing native/comtypes route.

Full typed validation W PID6728 contradicts a blanket typed-route fix: all four
mate steps report successful ranges/saves, but CloseDoc still returns
RPC_E_SERVERFAULT; event1000 at12:20:32 again records mfc140u.dll c0000005
offset0x23dc91. Reopen verification never runs. Source hash audit reports four
formal assembly files changed since the frozen input collection (AP45, stages
1/2/3); the MR12 task is actively editing its own PID42248. All trial loaded
document/path checks and save targets were private; do not claim formal hashes
unchanged or attribute changes without fuller chronology. Frozen private inputs
remain controlled independently of current formal source drift.

W launcher also printed IUnknown-release warning. Verification should be fully
complete before test calls next time; initial connection was started while the
launcher handle still reported running, though mate edits began after its final
manifest. Retain this timing confound. A typed single/three-mate pass is not
proof of robust prevention. Next isolation: nested mate read versus save, COM
object release before close, and a repeat with strict launch-completion ordering.

Captured owned W post-fault MiniDumpNormal and cleaned only its held process
after exact native-fault and creation-identity checks. Source differences are
recorded rather than used to assert a false preservation result. No CAD save
or call was issued after the native exception; other live processes untouched.

X PID36520: strict launcher-completion ordering; same frozen inputs and complete
typed sequence as W. Explicitly delete nd/nf/data/fresh/d/root wrappers after
repair and collect garbage, then collect prior execution namespace cycles in a
separate MCP call before obtaining fresh wrappers and CloseDoc. Repair and both
collection calls succeed; CloseDoc still returns RPC_E_SERVERFAULT. Event1000
at12:25:11 is dcu3d59.dll c0000005 offset0x11073. Thus the tested Python wrapper
retention and launcher overlap are not necessary for this solver failure.
This does not exclude every internal/native lifetime issue. No cold reopen was
attempted after fault. Local normal dump retained and only owned process cleaned.

Source preservation flags in later trials compare against the original frozen
collection's formal-source hashes, not an atomic baseline at each trial start.
Formal CAD is actively changing independently in the MR12 session. A false flag
does not itself attribute a write to this test. Keep frozen private-input hashes
as test-state proof; record live formal drift separately and never claim those
formal files remained unchanged. Future audit should take fresh per-trial
readable source baselines with timestamps without altering the private inputs.

Next meaningful comparisons are different native mate creation/update methods
and exception-time stack capture, rather than treating another successful
single trial as proof of global safety. No demonstrated full fix yet.

Debugger availability corrected by inspection: classic Windows SDK Debuggers
paths are absent, but installed Microsoft.WinDbg Appx contains amd64/cdb.exe.
Offline CDB analysis of X's live post-fault normal dump explicitly reports
"Minidump doesn't have an exception context" / HRESULT0x80004002. Its selected
thread stack is NtUserWaitMessage/CAmApp::Run, NOT the original solver fault.
Do not interpret the nearest exported UI-loop symbol as the fault caller.

Prepared local watch_owned_exception.py for an identity-checked owned test PID,
with held process handle, exact executable/start-time checks, local-only symbol
path, AV event dump/exception context/stack capture and debugger detach. It
launches no CAD, changes no global debug/registry settings, and writes no formal
model. Syntax/CLI checked; live capture and detach behavior not yet validated.
This preparation is not evidence that an exception-time stack has been captured.

Y live debugger trial: initial30-second readiness timeout occurred before mate
edits. Same owned PID44328 reused after verified debugger detach, without CAD
relaunch or file recopy. Second debugger attaches successfully; full typed mate
flow/GC run. During CloseDoc, CDB reports "Critical error detected c0000374"
then an80000003 diagnostic breakpoint in ntdll. AV-only capture filter missed
this earlier heap-corruption stop. MCP wait times out while debugger pauses CAD;
watcher detaches, then CAD exits with event1000 ntdll.dll c0000374 offset117eb5
at13:58:08, matching historical heap-fault signature. This is actual native
process exit, not investigation-forced termination. Other two CAD PIDs remain.

No exception dump captured in Y. Attempted context capture rejected missing
process (OpenProcess87) after authoritative exit; no stale-context claim. CDB
console is direct evidence of heap-corruption detection before a later AV,
not proof of the earlier corrupting write or a particular heap block. Capture
handler now also covers subsequent break-instruction events (bpe), to save the
diagnostic breakpoint context/stack automatically and detach without a manual
waiting interval. Live validation of this additional handler remains pending.
