# New received CloseAllDocuments case: PID46576

The user supplied the rack workspace's crash analysis and complete log archive.
The archive manifest verifies against all listed SHA256 values. Its15 entries
contain Windows events, Python/COM call reports, exact submitted code and model
verification results. There is no native dump entry. A preserved copy plus its
prior mirror/rename history is under ignored `current-close-46576` evidence.

## What the evidence establishes

- 2026-10-14 20:25:26–20:27:21: eight dynamic parameter cases and restoration
  return success in46576. The exact script is in server47096's log.
- 20:28:44: server19664 attaches to46576, enumerates already open documents,
  modifies support-bar custom properties and successfully saves the documents.
- Its script fails at line7, `CloseAllDocuments(True)`, with RPC_E_SERVERFAULT
  (-2147417851). The following retirement/move/open/interference-verification
  statements in that request did not execute.
- Windows event1000 records mfc140u.dll c0000005 offset23dc91 at20:28:51,
  followed by ntdll c0000374 in the same PID/creation identity at20:30:53.
- Additional history server35784 reads the still responsive instance at20:30:26
  and attempts Save3 at20:30:43. That later operation fails with RPC error.
  A native/server fault therefore did not prevent a subsequent caller from
  operating the same CAD process. Responsive UI is insufficient proof of health.
- A new managed PID1772 loads the saved model and passes cold verification,
  including zero physical interference. This proves a saved-model usability
  result, not elimination of the prior process-state crash.

This is a new case, distinct from40588's18:39 CloseDoc exception. The MFC offset
matches a previously reproduced native mate/close signature, but equality of
fault location alone does not establish the same corrupting operation.

## New history available for controlled replay

The additional log shows mirror-component creation attempts, three
ModifyDefinition calls, multi-document file/equation alias renaming, and later
dynamic validation. It contains no IsAdvancedMate conversion for46576. Thus the
existing distance-mate workaround cannot be assigned as its cause/fix from this
log alone. The previous40588 layer-pattern fixture is also not this renamed,
mirrored industry-model state.

The supplied dynamic script switches root/beam/frame/brace documents, updates
height, crossbar spacing, beam span and horizontal brace length, then restores
baseline values. Those operations and the subsequent Save3/CloseAll sequence
are now exact replay inputs. A faithful test requires privately frozen versions
of all referenced native models; the zip supplies observations but no CAD bytes.
Do not operate1772 to obtain an in-memory snapshot or change its configuration.

Any fatal RPC/native exception ends CAD calls for that owned process; do not
save/continue because it responds.

## Completed private controls: BJ and BK

Eight native files were copied into an immutable frozen input set and separate
mutable private fixture. Existing document references were rebound to the
private fixture before opening; all actually loaded document paths were checked
to be private. These are saved files obtained after the original crash, not a
claim of an identical crash-time memory or file snapshot.

- BJ, owned PID47164: cold open, original support-bar property edits, Save3 of
  all eight loaded documents, and CloseAllDocuments(True) passed. No documents
  remained open; the empty owned instance exited normally.
- BK, owned PID46816: a restored frozen input set, all eight original dynamic
  parameter cases, restoration of baseline values, the same property/save
  sequence and batch close passed. This owned instance also exited normally.
- All eight BK cases match the original recorded dimensions, instance counts,
  sorted physical placements, pattern flags and constraint status within the
  comparison tolerance. JSON is not byte-identical: ordering/names and floating
  point representations differ. This is physical-result equivalence, not proof
  of identical native process state.
- The immutable source hashes remained unchanged. The event1000 audit found no
  native fault for either owned PID. Existing1772/42248 were not operated and
  retained their creation identities. No owned CAD/debugger remained running.

Ignored evidence: `report-bj.json`, `report-bk.json` and
`bj-bk-event-audit.json` under `test-results/remaining-fault-correlation/`;
the case subdirectory contains the input manifest, adapted replay scripts,
`bk-dynamic-observations.json` and `bk-physical-comparison.json`.

These controls have not reproduced the original failure and do not establish a
fix. They show that the saved model plus the immediately preceding eight-case
parameter sequence is insufficient to reproduce it in the tested fresh state.

Read-only discovery also located `before-mirror-pattern-20261014-200615`.
Its contents were frozen with SHA256 in `frozen-before-mirror/` and
`before-mirror-manifest.json`: nine actual native models plus property templates
and eight lock artifacts. Lock artifacts are evidence only, not replay inputs.
This enables the next bounded investigation of original mirror creation and
multi-document native renaming before close. The directory is a saved backup,
not a full snapshot of the original process memory.

## Remaining evidence limits

The archive's stack is the Python/COM invocation stack, not the native C++
exception stack. WER dump access/missing data is explicitly recorded in the
supplied analysis. The exact original corrupting write remains unproven.
Read-only discovery found SolidWorksPerformance.log and crashsolutions.xml;
the examined files contain no usable crash-time C++ stack. This is not a complete
inspection of an exported SOLIDWORKS Rx Reliability/Problem Capture package.
Rx remains a diagnostic avenue, so absence of a Windows dump must not be treated
as proof that no additional evidence can be obtained.

The archive review itself did not operate CAD. Subsequent BJ/BK controls used
only owned instances and private files as described above. New evidence enables
a distinct investigation; it does not certify the previous failure as fixed or
retrospectively complete the root-cause goal.
