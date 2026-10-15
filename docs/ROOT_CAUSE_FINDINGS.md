# SolidWorks crash findings — updated2026-10-15

## Recent other-session audit — 19:10 Taipei, updated after 19:43–19:46

The user reported repeated errors and SolidWorks exits in `後推式貨架 (2)` and
`MR12 叉車`. Read-only MCP logs, saved thread outputs, process identity records,
and Windows events show several different mechanisms. No CAD operation,
restart, or configuration change was performed in either chat for this audit.

- Both chats retain a `GetDocuments()` list and continue querying its document
  wrappers after an earlier `CloseDoc` may have unloaded dependent documents.
  MR12 PID18088 fails at `GetPathName` at14:31:44; rack PID51148 fails at the
  same operation at16:53:37. Both return RPC_E_DISCONNECTED (0x80010108) and the
  current MCP records a whole-PID native-fault quarantine. Their subsequent
  exits are explicit recovery actions: MR12 `Stop-Process`, rack Alt+F4 after
  checking the process was still responsive. This is not proof of spontaneous
  native crashes. Microsoft's [COM code definition](https://learn.microsoft.com/en-us/windows/win32/com/com-error-codes-3)
  describes an object disconnect, not an assertion that the process crashed.
  A stale document wrapper is a supported hypothesis, not a reproduced cause;
  isolate and verify that document-lifetime sequence before relaxing any
  native-fault protection.
- MR12 PID37424 explicitly executes `ExitApp()` at17:29 after save/unload.
  Rack PID14708 is explicitly stopped during recovery from blocked loading.
  Do not count these intentional closes as evidence that MCP spontaneously
  terminated SolidWorks.
- MR12 PID37312/start09:30:09.155Z disappears between the last successful call
  at18:55:31.384 and the failed connection at18:59:02.017 (local times). Its
  last script samples MotionStudy time/transforms and has no close/exit call.
  A subsequently located owner receipt records its native error-report process
  PID14820, parent37312, created at18:56:27.817552, and the message that
  SOLIDWORKS stopped unexpectedly. The displayed fault module was blank; the
  owner recorded unchecking report transmission and closing the report. This
  establishes an observed native error report for the exact session, despite
  no corresponding crash/exit event in the scoped Windows queries. Exact exit
  time/code and a native dump remain unavailable; the last successful Motion
  read is not proven causal. The receipt is preserved in the
  [updated MR12 correlation](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/forklift-34632-close-doc-correlation.json).
- A separate MCP backup defect is confirmed: MR12's
  `AppData/Local/SWMCP/d6487dff014ce049/worker-startup.json` still reserves
  PID2836/start2026-10-12T12:51:28.718Z, while no `monitor.json` exists.
  `ensure_recovery_worker` refuses the newer target before creating a worker;
  the audited logs contain172 matching warnings. This establishes failed
  independent-backup startup, not a causal link to CAD exit. The reservation
  has not been removed and the live chats' runtime behavior is unchanged.

The [shared runtime audit](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/shared-runtime.json)
finds no automatic ExitApp/termination path for an existing target on timeout,
cancellation or quarantine. Arbitrary caller-supplied scripts can still request
ExitApp explicitly, as above. Sixteen
[offline recovery-design regressions](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/recovery-retirement-design-offline-v1.json)
pass, including reproducing the reservation rejection in the current service
with fake dependencies. They do not constitute a deployed fix or native CAD
validation. The subsequent isolated implementation adds worker/target identity,
startup-token and conservative process-inventory checks; its verified status is
recorded below. Removing an unconfirmed reservation alone could allow a delayed
old worker to bind the new session target.

The [MR12 audit](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/forklift.json)
records six PID cases and their source paths/lines; the
[rack audit](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/rack.json)
separates native events, later RPC loss, deliberate cleanup, and the live session.
The
[normalized Windows event inventory](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/normalized-crashes.json)
contains30 crash events since October14, of which22 exactly match this chat's
separate reproduction manifests. Those22 must not be attributed to the two
working chats. Rack PID1772 has a distinct recorded SLDMODU native exception;
the earlier rack sensor event24437 matches the module version, exception code
and fault offset reproduced in this chat's private instance. That match does
not establish the original sensor's exact target/interface state. Neither fact
explains every recent exit.

At19:05:20 a bounded, read-only OS observer began holding query/synchronize
handles for rack38232 and MR12's replacement34632, after checking PID, creation
time, image and the respective session manifests. It performs no COM call,
debugger attachment, termination, or UI control. The
[observer status](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/process-exit-observation-v1.json)
subsequently captured34632's kernel exit time/code. It cannot retroactively
fill37312's gap or identify an exit initiator or root cause alone.
The exit-time/code API was checked against a harmless child exiting with23.
Original root-cause controls and safe backup-recovery regression work remain
open; this audit is not a declaration that all crash or backup issues are fixed.

### MR12 PID34632: native CloseDoc failure, then owner cleanup

The exact identity is PID34632/start `2026-10-15T10:59:45.358Z`. At19:43:08.859
its own MCP executes `prepare_ap33_native_drag_review.py`; line11 loops over
private probe assembly titles and calls `sw.CloseDoc(title)`. Windows
Application Error1000, record25056 at19:43:18.556, records this same process
with `c0000005`, unknown module and offset `0x108`. WER records25057/25068
share report273da92c-1e07-4bca-a816-69fca666d16f. At19:43:33.129 the MCP log
returns `RPC_E_SERVERFAULT` (`0x80010105`) from that CloseDoc line and records
`native_fault_quarantined=true` for the same PID/start. The native error thus
precedes the final process termination.

At19:45:52.502 the MR12 owner explicitly runs
`stop_faulted_owned_solidworks.ps1` with PID34632 and its expected start time.
The script checks executable/start identity and then calls
`Stop-Process -InputObject $targetProcess -Force`; its receipt confirms exit.
The independent held OS handle records exit at19:45:52.839 with
`0xffffffff` (-1). That final code belongs to deliberate post-fault cleanup,
not the earlier access-violation code. The owner then starts its replacement
PID43932/start11:45:53.954Z. This investigation's separate baseline24588 starts
at11:45:58.673Z, after both the native fault and cleanup.

The [joined call/event/cleanup evidence](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/forklift-34632-close-doc-correlation.json)
includes original paths, line numbers, source hashes and the complete failing
script; [saved thread commands](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/forklift-34632-command-evidence.json)
confirm the actual owner cleanup invocation. The exact failing title/loop index
was not emitted before each CloseDoc, and no original exception-state dump is
available in this audit. Read-only access to the exact WER ReportArchive
directory named by the event was denied; its event metadata remains preserved,
and no permissions or security settings were changed. Therefore this is a confirmed native failure during
the CloseDoc call, not proof of its first corrupting operation, a particular
model, or a Python binding defect. Nor does the separate backup-startup warning
establish that missing independent backup caused the crash. The older stale
document-wrapper hypothesis for18088/51148 is not automatically this case's
cause, and the fixes for other close failures are not acceptance for34632.

### Follow-up log classification and isolated recovery acceptance

The [bounded follow-up audit](../test-results/remaining-fault-correlation/other-sessions-audit-20261015/other-sessions-since1200Z-1239-v1.json)
covers20:00–20:39:36 Taipei. MR12 has five functional/precondition assertions;
rack has one external-reference assertion. Their HRESULT fields are null. A
successful MR12 `CloseAllDocuments(True)` at20:33:18 leaves no documents and is
followed by use of the same CAD identity; it is not an application exit. The
explicit-UTC Windows query finds no matching new native event in this window.
This distinguishes these failures from the earlier34632 native exception; it
does not certify the models or rule out every unrecorded native fault.

The exact37312 CXPA session ZIP is22 bytes with zero members. Available bounded
log searches add no native stack. The report preserves this missing evidence
rather than treating the report filename as a usable dump. It also records15
new MR12 recovery-reservation warnings separately from CAD failures.

Recovery fencing is implemented in isolated commit `b64a82b2dad927fd2a98a820dadb37f46261ad14`.
Own PID24588's real lifecycle, dirty-part snapshot, original/snapshot reopen and
normal ExitApp acceptance pass: the original remains2mm and the recovered copy
contains the unsaved3mm change. See the [native backup result](../test-results/remaining-fault-correlation/sensor-private-valid-part-v1/recovery-backup-response.json)
and [reopen/normal-exit result](../test-results/remaining-fault-correlation/sensor-private-valid-part-v1/backup-reopen-exit-response.json).
The monitor reads AutoRecover=true, Backup=false and the native one-minute
interval without changing those preferences. The actual MR12 reservation is
untouched; this acceptance does not establish backup restoration in that chat.

The isolated `codex/crash-recovery-validation` branch combines recovery fencing
with opt-in exact-title CloseDoc breadcrumbs. Published commit
`1aff59de3ce85d120f9d3399700335236d8e5339` passes373 software tests. Its first
combined run's inventory-churn refusal remains preserved; the bounded retry
change is test-only, and production still refuses uncertain worker inventories.
This branch is not deployed to the live MCP. Neither tracing nor reservation
fencing is presented as a native CloseDoc crash repair.

## Native reproductions and scoped fixes

The investigation reproduced multiple native failure paths on SOLIDWORKS 2023 SP5
(31.5.0.52), using separate owned instances and private model copies. MCP/API
operations trigger them; the faults occur inside the native CAD process.
This is evidence for specific failing API/model-state paths, not a finding that
every historic crash has one cause or that all MCP operations are safe.

The newly reconstructed40588-history case is still under investigation. A
direction edit alone closes successfully; the following combined request makes
the traced CG control fail close. CL later reproduces equation51 and passes
close with tracing off after a local setup error/reconnection. Fresh uninterrupted
trace-on CM also reproduces equation51 but passes close, preserving the same
seven input hashes and original CAD script bytes as failed CG. Trace-off CN
reproduces the native close fault and supplies a validated full-memory dump;
tracing is not necessary. One fully staged early refresh passes a
reduced native matrix, but a simplified atomic wrapper fails and was removed.
The CJ continuation's full construction and separate CK saved/cold acceptance
now pass; fresh uninterrupted full staged replay CO and separate saved/cold
acceptance CP also pass on the integrated observer runtime. See
[CJ_CK_CL_NATIVE_RESULTS.md](CJ_CK_CL_NATIVE_RESULTS.md). The older
saved-state-only negative controls below are historical, not a reason to stop
the current failing replay. See
[DRIVEN_MATE_EVALUATION_TDD.md](DRIVEN_MATE_EVALUATION_TDD.md) for current gates.

A separate sensor-query native fault is now correlated to Windows event24437
and the actual MCP response: a script caught RPC_E_SERVERFAULT and printed it,
so execute_python incorrectly returned SUCCESS. Two new fake-CAD regressions
first failed on the pre-observer candidate. The observer is now integrated locally,
with311 passing tests including tracing on/off, thread isolation, trace-hook
preservation and caught-fault stdio restart. Other chats' loaded servers have
not been restarted by this investigation. See
[SENSOR_FAULT_FALSE_SUCCESS_TDD.md](SENSOR_FAULT_FALSE_SUCCESS_TDD.md).

At19:28 a new private empty-target sensor control explicitly succeeded at
QueryInterface(ISensor), bypassed the generated constructor, and then reproduced
the same sldapiu.dll31.5.0.52/RVA0x7223a2 access violation at `SensorType`.
The verified full exception dump records RCX=0 and a read from0xAD0. This
excludes swallowed interface-query failure for this reproduction. The MCP
returned an error and quarantined the exact PID; no later getter/save was issued.
A valid-target comparison remains necessary before attributing the failure
exclusively to the empty target. The faulted private PID52240 was closed only
after evidence validation, and no report was submitted. The linked sensor
document contains the per-member trace, dump receipt and cleanup verification.

CN's full dump now establishes a native use-after-free on the specific
後側_安裝高度 mate. Its busy moFeature_c allocation retains, at+0x170, a pointer
to an LFH heap block already marked free. Native destruction dereferences that
block's residual DCM3_node vtable in an MFC runtime-type query, dispatching into
do_move_to_list and reading0x100000007. Matching heap symbols, independent
Memory64List member/name reads and disassembly verify this chain. The exact
earlier free instruction remains unproven. CQ's after05/06 snapshots reproduce
the retained free reference despite successful close. CR's three checkpoints
now narrow its creation to the direction-edit request05: the independently
matched feature has a null member before that request, while an additional
busy object with the same matched name/caption retains a free API allocation
after it. That same reference survives the early equation refresh, even though
all functional geometry/save/close checks pass. The helper repairs binding but
is not proven to cure native lifetime. See
[NATIVE_REFERENCE_LIFETIME_TDD.md](NATIVE_REFERENCE_LIFETIME_TDD.md).
CS then observes no retained pointer immediately after ModifyDefinition and
request-local cleanup, before explicit rebuild. CT splits that request boundary
but still observes a retained free allocation after rebuild/save; its next
snapshot shows the exact same address reused as a busy DCM solver object.
The lifetime predicate rejects this run despite complete functional/close PASS.
This disproves a simple request-boundary-release cure. CU's four within-run
snapshots now observe the same named mate null before and after EditRebuild3
and ForceRebuild3; an additional named feature retaining a reused solver object
first appears after the subsequent transform-observation/Save3 request. The
remaining interval is observation/save/context cleanup or related deferred
native work, not those two explicit rebuild calls alone. Observation and Save3
still require separate verification. No universal
ModifyDefinition guard or preventive fix has been claimed from close success.
CV separates observation and Save3: the link remains null after observation;
Save3 produces an additional busy named feature linked to a busy moCompFace_c,
whose MFC GetRuntimeClass convention is independently verified. That live
CObject link is not automatically a stale API proxy; its ownership is still
unclassified at that boundary. CV then fails a physical first-floor count assertion
with null HRESULT and no native fault marker/event. Its later full snapshot now
shows the same busy feature and unchanged member pointer targeting an LFH/free
block with residual DCM3_node RTTI. This independently confirms a latent dangling
reference in CV; separating observation and Save3 did not prevent it. The missing
component assertion is not proven to share that cause. After full-dump/hash and
exact process identity verification, owned PID33112 was deliberately terminated
without another CAD/save call. That cleanup is not a newly observed crash.
Do not label the failed functional run as a successful lifetime fix. The member's vendor field name/type was never
published; use native reference consumed by API cleanup/type checking as the
minimum verified description.

CW changes the editing history by setting the rear distance direction during
AddMate5 creation and omitting its later direction mutation. Its full22-request
replay passes17 functional cases; both early and late native checkpoints find
only the independently matched busy rear feature with a null+0x170 member.
CX matches the saved geometry and passes7 cold cases with another null native
checkpoint, but its complete acceptance fails at the held-handle exit gate:
the diagnostic CDB watcher omitted `-G` and held the target at its default
final process-exit breakpoint. This monitor defect was independently reproduced
and corrected with harmless Python controls, including preserved AV detection.
CY now completes that fresh cold replay with the corrected watcher: all11
requests, saved geometry before edits, all7 cold cases and rear rotations pass
from the same frozen CW inputs. Its late native checkpoint again finds a null
member+0x170 on the independently matched busy rear feature, with no unknown
matched features. Owned PID48928 exits with held-handle code0; the watcher
finishes naturally after6.29 seconds, with zero exact-identity fault events.
The [CY acceptance](../test-results/remaining-fault-correlation/current-close-40588/cy-cold-acceptance.json)
therefore completes the scoped CW fresh/CY saved-cold acceptance for this
editing recipe. CX remains failed, and CW's uncaptured OS exit code remains
an explicit gap. This does not identify the first free instruction or establish
a universal fix; the sensor native replay and historical attribution remain open.
See the [per-case evidence ledger](ROOT_CAUSE_CASE_LEDGER.md) for confirmed
causes, verified containment and remaining attribution limits.

A further built-in SaveAs containment gap has3 failing fake-CAD regressions:
native faults can fall through to another save API or lose the final marker.
The bounded rethrow fix now passes315 actual-source tests after CV's baseline
hashes were preserved. It changes no CAD save option or native memory. See
[DOCUMENT_SAVE_NATIVE_FAULT_TDD.md](DOCUMENT_SAVE_NATIVE_FAULT_TDD.md).
The actual
fault marker blocks a fresh no-COM guard while the failed CAD remains live.
See [CN_FULL_DUMP_NATIVE_DISPATCH.md](CN_FULL_DUMP_NATIVE_DISPATCH.md).

| Finding | Evidence | Prevention |
| --- | --- | --- |
| Imported-reference dependency query | `IModelDocExtension.GetDependencies` with `AppendImportedPaths=true` reproduces `sldapiu.dll` access violation at offset `0x8a24c0`; false returns an invalid scalar in the control. Failure also reproduced at approximately 64% committed memory. | Typed pywin32 guard blocks this exact query before invocation. Raw native calls can bypass it. |
| Existing distance-mate conversion followed by document close | Combined `IsAdvancedMate=true` / `ModifyDefinition` edits reproduce native solver/MFC failures. Exception-time dump shows an invalid read through `rbp=0xffffffff` during mate/feature/assembly destruction servicing `CloseDoc`. | Create fresh limit mates from the existing endpoints, rather than converting the old feature kind in place. Explicit identity-change acknowledgment is required. |
| Invalid configuration after prior rebuild | Frozen pre-repair rack files reproduce error61704 and, after horizontal rebuild plus failed diagonal switch, native purecall/abort during close. AM has an actual exception-stream dump showing c0000409 subcode7 and equation/model-update/close frames. Individual-operation controls close normally. | Preserve valid working equations while recreating the inactive configuration, validate/save a private checkpoint, then restore parent binding and resolve pattern members. AX passes the full frozen-input geometry, dynamic input, actual pattern count/placement, save/close/reopen workflow. |
| Memory pressure | Windows resource-exhaustion event independently establishes historical commit exhaustion. Native fault controls above also reproduce without exhaustion; successful fresh-mate control ran at higher commit usage than one failing control. | Respect explicit open-document memory-warning cancellation. Memory pressure does not explain every native failure. |
| Mate reference update plus equation recreation and old-child deletion | Owned BM/BP fail batch close with native exception dumps. BQ/BR/BS separate the interaction. Omitting refresh leaves invalid equation51; an in-place same-text update restores binding. | New helper preserves count/text/order. Fresh BV passes8 dynamic cases/save/close; separate BW passes saved baseline, changed input/restoration and normal close. See EQUATION_BINDING_CLOSE_TDD.md. |
| Timeout | One traced replay timed out during comtypes type-library loading. Filtering generated-code tracing allowed completion. | A timeout alone does not prove a CAD crash. Correlate the PID, last API, native event and process exit. |

The fresh-mate control preserves 68 component transforms exactly and completes
the original four-mate follow-up, save, close, reopen, saved-range verification,
second close and normal exit. The callable MCP implementation passes the same
workflow in trials AE and AF, including all three feature replacements. AF uses
a new owned process and restored frozen inputs. Both exit normally, with no
corresponding Windows crash event. The 233-test unit suite passes. The tool leaves
changes unsaved; the test explicitly saves only its private copies.

Important limits:

- Individual mate conversions passed; the combined conversion/close flow failed.
  Do not generalize this into a ban on all `ModifyDefinition` or all `CloseDoc`.
- The exception dump proves the native destruction fault, but does not identify
  the earliest corrupting write. Private vendor symbols and another-version
  comparison were not available. Vendor defect versus an unsupported conversion
  contract is not conclusively distinguished.
- Several older crash signatures have not been independently reproduced. A
  multi-hour gap after `ExitApp` does not establish that call as the cause.
- Backup overlap, typed-wrapper changes and explicit Python collection were
  tested in controls; these results are narrower than a universal exclusion.
- Model inputs were frozen private copies. Other sessions concurrently changed
  formal source files; source-hash drift was recorded, not represented as proof
  that the tests wrote those files. All loaded paths were checked before saves.

See [mate fault evidence](CONFIRMED_NATIVE_MATE_CLOSE_FAULT.md),
[dependency fault evidence](CONFIRMED_DEPENDENCY_API_FAULT.md), and
[configuration fatal-exit evidence](CONFIRMED_CONFIGURATION_FATAL_EXIT.md) for the trial
matrix, dump details, official API contract references and remaining limits.
CAD files, diagnostic logs and dumps stay local under ignored `test-results/`.

## Callable workaround

2026-10-14 18:39 produced a new, separately attributed rack-session crash:
Windows event1000 records PID40588 (0x9e8c) with unknown-module c0000005,
followed by KERNELBASE c000041d. That session's `generic-base-frame-report.json`
records RPC_E_SERVERFAULT from CloseDoc after Save3 and prototype copying,
before its subsequent restoration/editing statements. This is an exact current
call correlation, not proof of the earliest corrupting operation. This diagnostic
chat did not operate that PID. AX/AY's new owned repair processes have different
identities and no matching crash event. The new CloseDoc case remains an open
root-cause item; do not conflate it with the repaired configuration flow merely
because both involve document closure.

`recreate_distance_mate_as_limit` requires an already connected configured PID
and an already open assembly. It never starts CAD, saves or closes documents.
Arguments: absolute `filepath`, exact `mate_name`, `minimum_m`, `maximum_m`,
`distance_m` in meters, and `allow_identity_change=true`. It validates ordinary
mate type, endpoint selections and bounds before deleting, preserves endpoint
order/alignment/flip/name, creates a fresh limit mate with `AddMate5`, and
checks its range and rebuild status.

Feature identity and ordering can change; downstream references must be reviewed.
Failures after deletion report `partial_change=true`; callers must stop rather
than retrying blindly or saving the incomplete result. This optional tool does
not rewrite arbitrary `execute_python` scripts or migrate another session's
caller. Restart that session's MCP connection to load the updated tool.

The initial40588 saved-state controls included a pre-layer reconstruction with
recorded inputs and matching pre-refresh equations/pattern/component observations.
Those shortened controls did not reproduce a native crash; post-refresh beam
counts diverged (original6, replay7). The later discovery of an older18:17 input
and omitted live history now produces native failures. Full input provenance,
fidelity limits and current follow-up are in
[CURRENT_CLOSE_40588_CASE.md](CURRENT_CLOSE_40588_CASE.md). This case remains
unattributed rather than being declared another instance of an existing fix.

Paired stored/reconstructed pattern inspection finds matching seeds, zero skipped
instances and zero feature errors, but different generated-child inventories.
Fresh BF and retained-helper BG independently change enumeration6→7 through
balanced selection rollback/restoration without changing a feature property;
the reconstructed control remains7. Neither reproduces the native close crash.
The pattern cache/state difference is now measured, not inferred from an equation
count, and must still not be declared the heap-corruption cause.

The saved-state controls also show rear-standard selection access/restoration
alone regenerating6→7 components, and a passing uninstrumented two-MCP close.
These delimit that older input's behavior. The original exception dump and exact
crash-time dependencies are still missing, but a fresh failing native replay is
now available. The earlier blocker audit in CURRENT_CLOSE_40588_CASE.md is
explicitly historical and superseded. The broader goal is not achieved; verified
workarounds for other paths must not be generalized to unattributed events.

The separately received46576 batch-close case is retained in
[CURRENT_CLOSE_46576_CASE.md](CURRENT_CLOSE_46576_CASE.md). Its Windows events
establish access violation followed by heap corruption after a subsequent caller
continued Save3. Fresh private BJ/BK saved-state and eight-case dynamic controls,
plus BL's pre-mirror cold baseline, all close normally. Subsequent BM/BP history
replays reproduce native failures and BQ/BR/BS separate their interacting edits;
BV/BW validate the full in-place binding workaround and saved geometry. The
initial negative controls alone are not the final state of that investigation.

One confirmed diagnostic defect was corrected: execute_python failures previously
returned a traceback but persisted only success=False in the main log, losing
partial stdout/stderr. The updated handler records PID, HRESULT, script location,
traceback and partial output without another CAD call. Five failure-evidence
tests and full259-test discovery pass; a separate mocked process verifies actual
FileHandler persistence. That earlier change improves evidence collection, not
native crash prevention or attribution; it did not itself quarantine a faulted PID.

A subsequent containment candidate now persists native/RPC fault markers by
PID/start identity and blocks later MCP requests and new recovery-worker ticks
before CAD access, including across an MCP restart. Red/green boundary and real
stdio/fake-CAD tests verify the behavior; actual owned native-fault acceptance
now passes on CN. See [NATIVE_FAULT_QUARANTINE_TDD.md](NATIVE_FAULT_QUARANTINE_TDD.md).
This candidate does not identify or repair the first corrupting native operation.
Two backup cleanup paths also continued CAD queries/activation/close after an
escaping native failure. Red/green regressions now preserve the original failure
and skip those calls, while ordinary copy failures still restore the active view.
Full unit discovery passes311 after caught-exception observation is integrated. These confirmed MCP failure-handling gaps are
separate from attributing the first native fault; owned red controls reproduce
with independent recovery monitoring disabled.

Further46576 replay now has failing BM/BP controls and a tested in-place binding
workaround. The original script structurally mutates the live equation manager
inside its traversal, a crash risk explicitly documented by SOLIDWORKS. The
operational trigger and its red/green/native saved-state evidence are recorded in
[EQUATION_BINDING_CLOSE_TDD.md](EQUATION_BINDING_CLOSE_TDD.md). Its precise native
address differs from the original Windows event, and40588 remains unattributed;
neither limitation is removed by273 passing unit tests or by this new fix.

The40588 investigation has now resumed from a newly found18:17 backup and
previously omitted same-PID operations. BX reproduces a native close fault
after the earlier build/equation history, with an owned exception dump in
DCM node destruction. It stops before the later failed selection-access call;
that omission cannot explain this reproduced failure. The dynamic-state and
exception-address differences still prevent exact attribution to the original
40588 event. Reduced controls are in progress; see the dated continuation in
[CURRENT_CLOSE_40588_CASE.md](CURRENT_CLOSE_40588_CASE.md). The previous blocker
audit is historical and is no longer a reason to stop this new failing replay.

Reduced40588-history controls now separate a successful direction edit/close
(CD) from native close failure after the next equation/property/rebuild request
(CG). CH's staged early refresh passes six original physical cases and close,
while late repair (CB) and an atomic encapsulation (CI) fail. CI's fake tests
were green but its native test was not; the unverified function was removed.
CO/CP verified the exact staged recipe's full functional construction and cold
acceptance. Later CQ/CR/CT/CU/CV snapshots show why those functional or close
passes alone are insufficient. The revised creation-time direction recipe now
passes CW's full fresh workflow and CY's independent saved/cold workflow,
including the bounded named-reference gates and CY's observed clean exit. See
[DRIVEN_MATE_EVALUATION_TDD.md](DRIVEN_MATE_EVALUATION_TDD.md). The operational
interval must not be generalized into a ban on ModifyDefinition or a claim
that every original native exception instruction has been attributed.
