# SolidWorks crash findings — updated2026-10-15

The investigation reproduced four native failure paths on SOLIDWORKS 2023 SP5
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
Exact rebuild/checkpoint/fresh-manager staging, full construction and cold
acceptance remain under validation in
[DRIVEN_MATE_EVALUATION_TDD.md](DRIVEN_MATE_EVALUATION_TDD.md). The operational
interval must not be generalized into a ban on ModifyDefinition or a claim
that every original native exception instruction has been attributed.
