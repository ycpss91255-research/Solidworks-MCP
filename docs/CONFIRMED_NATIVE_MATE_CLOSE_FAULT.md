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
