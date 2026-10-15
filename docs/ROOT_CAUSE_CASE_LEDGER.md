# Crash root-cause case ledger — 2026-10-15

The investigation has established multiple native CAD failure paths and separate
MCP containment defects. It has not established one cause for every historical
exit, or a universal preventive fix. This ledger distinguishes the observed
failure mechanism, a tested workaround, and remaining attribution work.

`LAB` below means the local, ignored
`test-results/remaining-fault-correlation/` directory. Native dumps and private
CAD fixtures are not published. Large evidence is retained on the authorized
SanDisk through verified workspace junctions; see [storage](DIAGNOSTIC_STORAGE.md).

| Case | Observed trigger / native cause | Authoritative evidence | Verified handling and limits | Remaining |
| --- | --- | --- | --- | --- |
| Imported-reference dependency query | The typed extension `GetDependencies` query reproduces `sldapiu.dll+0x8a24c0`, `c0000005`; the false-import-path control returns an invalid scalar. | Historical PID35832 and owned PID36872 event/call correlation; [dependency evidence](CONFIRMED_DEPENDENCY_API_FAULT.md). | Exact typed IID/DISPID guard rejects the query before invocation. Owned PID40524 verifies the guard, valid narrower inventory, and normal close/exit. Raw COM routes are outside that guard. | Native implementation versus lower-level COM marshaling is not separated; this does not prevent other dependency/API failures. |
| Existing distance-to-limit mate conversion | Combined edits followed by close reproduce MFC/DCM destruction faults. AA captures `dcu3d59+0x11073`, invalid read at `0x100000007`, with feature/mate/assembly destruction frames. | Frozen 230-file controls, AA exception dump, AD/AE/AF full acceptance; [mate evidence](CONFIRMED_NATIVE_MATE_CLOSE_FAULT.md). | Fresh limit-mate creation preserves endpoints, range and all 68 component transforms; complete four-mate follow-up, save, close, reopen and saved ranges pass. Callable tool verified in independent AF. | Feature identity/order changes require explicit acceptance. No universal ban on `ModifyDefinition`; earliest corrupting operation and vendor-versus-contract attribution remain unproven. |
| Invalid brace configuration | Prior horizontal rebuild plus failed diagonal switch leads to native purecall/abort during close; individual-operation controls pass. | AG–AM controls; AM exception stream is `c0000409`, subcode 7, with equation/model-update/close frames; [configuration evidence](CONFIRMED_CONFIGURATION_FATAL_EXIT.md). | Preserved-equation staged repair, saved checkpoint, parent binding and actual pattern placement pass AX; separate AY verifies saved geometry/matrices. | Repair is specific to the frozen fixture. A much earlier PID28724 fault with a multi-hour MCP gap is not attributed solely by matching signature. |
| Mate-reference changes, equation recreation and child deletion | BM/BP close faults reproduce the combined history. BO/BQ/BR/BS separate the interaction; omission alone leaves invalid binding in BU. | `LAB/current-close-46576/` comparisons and BM/BP dumps; [equation TDD](EQUATION_BINDING_CLOSE_TDD.md). | In-place same-text equation refresh preserves count/text/order. Terminal BV passes 8 dynamic cases and save/close; terminal BW passes 3 separate saved/cold observations. Both preserve frozen inputs; audited fault-event count is zero. | Original PID46576 has no original exception-state dump. A shared MFC detection site with CB does not prove the same first corrupting operation. |
| Rear distance-mate native lifetime | CN directly shows a busy named feature retaining a pointer to a freed allocation, then dereferencing its residual solver vtable during cleanup/type checking. CQ/CR/CT/CV observe retained-free or incompatible reused targets despite some successful closes. | CN full dump and [native dispatch](CN_FULL_DUMP_NATIVE_DISPATCH.md); [lifetime TDD](NATIVE_REFERENCE_LIFETIME_TDD.md); `LAB/current-close-40588/cv-late-native-reference-verified.json`. | Identity-bound quarantine stops subsequent managed calls after an observed fault. Early equation refresh and split requests are **not** verified lifetime cures. Creation-time rear direction now passes CW's17 fresh cases, CY's7 saved/cold cases, all three bounded native gates and CY's held-handle exit0. | This is a scoped recipe, not a universal lifetime guarantee. Exact first-free instruction is unknown, but is not required to establish the observed UAF. Original PID40588's unknown-module event is not retrospectively equated with CN. |
| Sensor-query native fault | Original PID48852 event24437 falls inside the actual sensor request: `sldapiu+0x7223a2`, `c0000005`, then caught `RPC_E_SERVERFAULT`. | `LAB/48852-sensor-fault-audit.json` and original call/reply; [sensor TDD](SENSOR_FAULT_FALSE_SUCCESS_TDD.md). | The consumed-exception observer fixes false SUCCESS and blocks later managed requests; mock and real-stdio regressions pass. This is containment, not a native sensor repair. | The compound expression's exact failing member and faithful native replay are unverified. Its later process exit has not been attributed. |
| CV missing component | First-floor acceptance expects 4 front beams but finds 3; HRESULT is null and no native exception was captured at that assertion. A later dump independently proves a dangling reference. | `LAB/current-close-40588/cv-failed-functional-audit.json`, `cv-late-native-reference-verified.json`. | Failed acceptance remains failed; the corrupted owned PID was retired without another CAD/save call after dump validation. | Missing-component cause and any causal link to the dangling reference remain unproven. It is not itself evidence of a spontaneous process crash. |
| Memory pressure | Historical System event2004 records virtual-memory exhaustion. Separately, native query failure reproduces near 64% commit; successful mate replacement ran at higher commit than a failing conversion. | [initial read-only audit](../test-results/crash-investigation-20261013.md), event time 2026-10-12 18:12:46; `LAB/cg-cm-close-memory-comparison.json`; dependency/mate controls above. | Explicit low-memory cancellation and observable resource waiting avoid blind retries. Physical availability and commit reserve are checked separately. | Pressure is real but not sufficient to explain every fault. A later scoped event2004 query with no matches does not exclude allocation failure. |
| Backup / MCP interaction | Native red controls run with independent recovery monitoring disabled. Separately, inspection and RED tests show recovery cleanup, save fallbacks and later requests could still access CAD after native faults. | [quarantine TDD](NATIVE_FAULT_QUARANTINE_TDD.md), [save TDD](DOCUMENT_SAVE_NATIVE_FAULT_TDD.md), actual CN quarantine proof. | Failure paths now preserve evidence and skip subsequent managed CAD access; ordinary binding/copy failures retain their appropriate cleanup. | Recovery is not necessary for the reproduced native paths. This is not a universal exclusion of backup/add-in/timing effects, nor interception of arbitrary raw COM inside a running script. |
| Intended shutdown, cleanup and timeout | BV/BW complete explicit empty `ExitApp`; CV is deliberate exact-identity OS cleanup. Historical PID18632 has both an `ExitApp` script and a native event, so is not a clean-exit control. A type-library tracing timeout is not itself a CAD crash. | Terminal reports/audits below; initial read-only audit; `LAB/current-close-40588/cv-verified-native-state-cleanup.json`. | Classify by exact process identity, call interval, native event/dump and held-handle exit, not tool SUCCESS or elapsed time alone. | Historical compound Save/Close/Exit scripts without sub-call markers cannot identify an individual failing API from timing alone. |

## Current acceptance evidence

These compact artifacts were inspected for this ledger; large dump hashes were
read from their completed verification records, not recalculated in this audit.

- `LAB/report-bv.json`: PID15976, 23 requests, `passed=true`, immutable sources
  preserved, final request `exit_empty_owned_instance`.
- `LAB/report-bw-resume2.json`: PID38848, 8 requests, `passed=true`, immutable
  sources preserved, final request `exit_empty_owned_instance`.
- `LAB/current-close-46576/bv-bw-physical-comparison.json`: 8 fresh and 3 cold
  cases, dimensions/counts/patterns/constraints/positions match within 1e-5 mm.
  Exact component names are outside that comparison. The accompanying
  `bq-bw-event-process-audit.json` records zero matching faults and no remaining
  tested CAD PID at its recorded observation time.
- `native-close-control-matrix.json` is an earlier intermediate snapshot: it
  still says BU is running and omits BV/BW. It is **not** current terminal proof.
- `LAB/current-close-40588/cn-native-quarantine-verification.json`: a fresh
  metadata-only object blocks PID39868's exact still-live faulted identity;
  `cad_calls=0`, `com_binding_created=false`. Validated CN dump SHA256:
  `a5c111e531b17db833223d29fd164f52646719efb7f8e1dbc92f94c1ff976604`.
- CV later native proof records SHA256
  `835576d3ae1053164ed72d53cfc56afe193b533faca27464477a3626444c0ee1`.
  Its cleanup record verifies held-handle exit, zero subsequent CAD/save calls
  and no other terminated process. That intentional cleanup is not a new crash.
- `LAB/document-native-save-production-suite.txt` records **315 tests passing**
  in 19.043 seconds, after the three SaveAs native-failure RED regressions.
  Current `automation/documents.py` was independently hashed for this ledger:
  `5f51f6537cc0dbe00a9f5f72156660556ec83451615cc61ec4a0a7868e24a083`,
  matching `document-native-stop-applied.json`. These tests prove their stated
  containment behavior, not universal native CAD safety or migration of loaded
  MCP processes in other chats.

## CW and CY scoped acceptance passed; CX exit-monitor failure retained

Own PID25376/start `2026-10-15T08:34:11.998000+00:00` completed all22 requests.
`cw-functional-acceptance.json` verifies both six-case matrices, all five
first-floor cases, rear rotations, source/runtime hashes and save/close results.
The candidate sets rear distance
direction at creation and omits the later direction mutation while retaining
the full workflow. It changes editing history, not just debugger timing.

The completed `checkpoint-cw-after_rebuild_save/native-gate.json` has one
independently matched busy `moMateDistanceDim_c` with null member+0x170, no unknown
matched feature, and SHA256
`b2540339db954020ed5add72d62729e5800f7ad74f7a88ebea9808e5daf68715`.
The later `checkpoint-cw-after_functional/native-gate.json` finds the same busy
named feature with null member+0x170 after all17 cases; its full dump SHA256 is
`87c885622782e806eba17ba9b5285380162b34a9facd1f12ba7c268af7dbdfec`.
Both full dumps were bounds/hash/heap verified. `cw-full-native-acceptance.json`
joins these gates with functional acceptance and the now-absent owned process.
No native exception was captured and the exact-identity event audit has zero
matches. The watcher detached after the ExitApp response, so the actual final
OS exit code is unavailable; that observation gap is explicitly retained.

CX independently matched saved geometry and passed seven cold cases plus a
late native checkpoint (matched busy rear feature member+0x170 null). Its full
dump SHA256 is `80253a23c318507238696692def056e53932d86edd3d38227852be676ce93e32`.
Root and batch close returned, but the full acceptance **failed**: CDB's
default final-exit breakpoint held the target at `NtTerminateProcess`, so the
held-handle exit gate timed out. The missing `-G` flag was reproduced/fixed in
an independent harmless-Python RED/GREEN comparison; this is a diagnostic
monitor defect, not evidence of another native CAD crash. CX was released by
watcher detach and later verified absent, without a captured OS exit code.
The terminal failed report and rejecting verifier remain preserved.

CY owned PID48928/start `2026-10-15T09:29:43.212000+00:00` now passes all11
requests from the same seven frozen CW inputs, preserving CX's CAD request
ASTs/order. The [independent acceptance](../test-results/remaining-fault-correlation/current-close-40588/cy-cold-acceptance.json)
verifies geometry before edits, all7 cold cases and rear rotations, source/runtime
hashes, root and batch close, and actual normal process exit. Its late
[native gate](../test-results/remaining-fault-correlation/checkpoint-cy-after_cold_functional/native-gate.json)
finds one matched busy rear feature with null member+0x170 and no unknown
matched features; full-dump SHA256 is
`3cb1f0fe824693369e69babb8b182becada6ca8f4a52a938c8b0212a9af9dbfe`.

The same PID/start/image-verified handle held across ExitApp signals with
exitcode0. The close watcher completes naturally without a detach request or
fault dump; observation takes6.2945 seconds. The event audit extends beyond
handle closure and records zero exact-identity CY matches, with CG still a
positive control. CW+CY therefore pass the scoped fresh/saved-cold recipe,
including the named-reference gates. This neither converts failed CX to PASS
nor fills CW's exit-code gap, and it does not certify every native allocation.

## Completion boundary

The bounded original sensor audit now identifies a concrete next control:
`LAB/sensor-fixture-candidate-audit.json` records the original dimension-sensor
PropertyManager with an empty target/value, its confirmation, and the subsequent
query of `Sensors1`. The sensor was later deleted and saved, so the pre-sensor
root-only backup is not the lost fault-state fixture. A fresh private valid-target
versus empty-target sensor comparison, with separately traced getters, is the
next causal test. The valid-target controller has started, with actual UI and
native getter acceptance still pending. These UI observations support a hypothesis; they do not yet
identify the failing getter or prove that an empty target caused the exception.

The broad root-cause goal remains active. The CW/CY candidate verdict is scoped
PASS; next work must investigate the sensor sub-call and any repeated CV functional
failure, and record final per-case disposition. Missing original exception-state
dumps limit historical attribution; a shared detection address cannot fill that
gap. Unknown first-free provenance does not invalidate the directly observed
UAF, and does not justify claiming a universal fix either.

All live reproduction uses owned PID/start identities and private frozen copies.
No other session is operated or restarted for this ledger. The retained geometry
assertions are automated acceptance of native CAD results; they are not labeled
as native Design Study or Design Checker tests. Scope-specific RED/GREEN tests,
native evidence and saved-state verification remain separate requirements.
