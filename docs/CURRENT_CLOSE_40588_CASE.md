# Current CloseDoc crash: PID40588, 2026-10-14 18:39

## Established event and call correlation

The rack session's `generic-base-frame-request.json` first saves the already open
generic assembly, copies it to `generic-first-layer-prototype.SLDASM`, and calls
CloseDoc. Its report records RPC_E_SERVERFAULT at CloseDoc (script line5).
The statements that restore a backup, open it, delete equations/features and
change properties follow that call and therefore did not execute in this failed
request. ExitApp is not the failing operation.

Windows application event1000 records the same PID40588 (0x9e8c) and process
creation identity: unknown-module c0000005 at18:39:38, then KERNELBASE c000041d
at18:39:51. Report IDs are1d8e09ae-cb1c-48b5-b767-6c3899833ebf and
8dea7d4e-1c4e-47f2-8f47-5d4ade856f37. These correlate a native failure with
the CAD call, but do not identify the first corrupting operation or instruction.

The ReportArchive entry contains Report.wer. Its listed temporary dump
`WER.c85a4584-a101-4e4d-bc88-da14b1c055eb.tmp.dmp` is no longer present.
No ACL/security settings were changed to obtain it. The nearest available global
memory trace sample is27.36seconds AFTER the initial crash (77.88% commit);
it cannot establish the original PID's memory pressure at the failure instant.
No exact contemporaneous per-call memory/exception dump is available for40588.

## Retained inputs and fidelity limits

The prototype assembly was copied at18:39:36 before the failing close. It is
retained with SHA256
`96bd99c66a8086bc3ac93df8833b6f66ea9ef7cd852a487a5b027fa7e175183e`.
The earlier `generic-before-first-layer-height.SLDASM` backup is also retained.
Scripts/reports/logs are copied before experimenting; provenance and hashes
are in `current-close-40588/input-manifest.json`.

Six transitive native dependencies were copied from their currently available
files and rebound into a private fixture. Their versions are **not** established
as identical to the crash-time bytes. Dependency hashes and timestamps are in
`dependency-snapshot.json`. An end-part retains a missing old context reference
to `D:/push_back/1重型货架.SLDASM`; that file does not exist. It was recorded as
missing, not substituted with a different assembly or claimed repaired. Existing
resolved references and every loaded document were checked inside the private
fixture. All CAD calls target this diagnostic chat's own PID.

## Completed controls

| Trial | Owned PID | Control | Result |
| --- | --- | --- | --- |
| AZ resumed |38168| Fresh open of retained saved prototype, Save3, filesystem copy, CloseDoc | Save True/0/0; close and normal exit succeed |
| BA |33400| Saved prototype plus original preceding pattern AccessSelections/ModifyDefinition/rebuild, then save/copy/close | Succeeds; before-edit pattern count3 matches original |
| BB |3836| Pre-layer backup, original native pattern-building and count scripts, then refresh/save/copy/close | Succeeds, but layer inputs1/1 differ from original4/3; not a faithful full replay |
| BC |25360| Pre-layer backup, pattern building, restored recorded layer inputs, count/refresh/save/copy/close | Succeeds; pre-refresh equations, pattern records and six beam occurrence records exactly match original |

BC restores front/rear layer counts4/3, first heights800/500mm, subsequent
spacing500/600mm, installation-height properties217.043mm. The exact original
count observation is retained. `bc-observation-comparison.json` shows equal
equations, equal pattern settings and equal component records before refresh.
After refresh, BC produces seven beams while the original request reported six.
This is a measurable divergent model state even with matching earlier observable
values. It is not proof that the missing beam caused the native crash.

All four owned controls stop backup monitoring, use fresh PID-bound MCP stdio,
capture script/operation/memory traces, attach a debugger only to the owned
identity, choose cancellation for any memory warning, and stop on first failure.
No native crash was reproduced in these controls. Event1000/1001 audit contains
the previously attributed40588 events, with none for the four test PIDs. All
owned CAD/debuggers exited. Other live session PIDs42248/46576 were not operated.
The initial AZ attempt stopped before opening at an unmapped missing reference;
its console also hit CP950 encoding. AZ resumed on the same still-empty owned
PID after recording missing references and fixing diagnostic output encoding;
it is not a pristine single-pass first attempt.

## What is still unproven

These controls contradict assigning this failure to CloseDoc alone or to the
last pattern refresh alone for the tested private state. They do not exclude
effects of earlier session edits, missing crash-time dependency bytes, native
internal references/caches, UI actions, add-ins or memory pressure at the actual
failure instant. Do not globally block ModifyDefinition or replace the CAD close
operation with force termination on the strength of this evidence.

The next bounded comparison is the stored-pattern instance/seed/skipped-state
difference between the saved prototype and rebuilt BC fixture. A failing native
replay and actual exception context are required before calling that difference
the crash root cause. The broader root-cause goal remains open.

## Paired seed/member inspection (BD/BE/BF)

BD initially stopped on a diagnostic assumption: SeedComponentArray returned
CDispatch, not a generated-class Python name. Explicit QueryInterface showed
these seeds support IFeature and identify Reference/ReferencePattern features.
The same owned PID47420 was resumed after balanced selection release; it is not
a pristine inspection of the initial state. No native fault occurred in that
diagnostic error. BE PID35876 is a fresh reconstructed-fixture control.

The seed and skip comparison shows no missing seed, no skipped instances and
no feature error in either fixture. Both standard patterns use the first-tier
pattern instance as their seed. The stored front standard pattern advertises
three total instances, but initially has only one generated ReferencePattern
child. The reconstructed version has two generated children. This concerns
observed model/feature state, not a proven heap-corruption mechanism.

BF PID40408 restores the immutable saved-prototype clone and records enumeration
before any pattern selection access. It starts with6 beams. Sequential balanced
AccessSelections/ReleaseSelectionAccess on front-first, front-standard and
rear-first keeps6; after rear-standard it becomes7. The inspection changes no
feature property and performs no explicit rebuild or save, but selection rollback
and restoration can regenerate the model. Thus it must not be described as a
passive read-only measurement of unchanged component state. BE's reconstructed
fixture stays7 before/after all four probes. Both close and exit normally.

Evidence is `prototype-before-after-inventory.json`,
`rebuilt-pattern-inventory.json`, `report-bf.json`, `report-be.json` and their
script/debugger traces. The exact safe next isolation is rear-standard access
alone versus the preceding selection sequence; this model-state change still
does not reproduce40588's CloseDoc exception.

Retained helpers in `solidworks_mcp/diagnostics/pattern_inventory.py` bind the
returned seed by explicit interface IID, not its Python proxy class name. Only
E_NOINTERFACE permits trying the alternate seed interface; native/server faults
stop. The selection scope releases access after a plain diagnostic exception,
and performs no further COM cleanup after a fatal server/RPC fault. Callers must
verify their owned PID and private paths. The helpers never start, save, close
or modify a feature property. They are opt-in diagnostics, not an automatic
pattern-repair or crash-prevention hook.

Four retained regressions cover CDispatch/IID binding, no interface retry after
server fault, release after a plain read failure, and no COM cleanup after a fatal
server fault. The initial three were RED before implementation, then GREEN;
full suite254 passes. These unit results verify diagnostic safety/contract
handling, not proof that the original crash has been fixed.

BG PID47768 restores the same immutable prototype and uses the retained helper
implementation in a fresh owned MCP. It independently repeats the exact
component-count stages6,6,6,7, with6 before and7 after, then closes/exits normally.
`retained-helper-inventory.json` and `report-bg.json` retain that live validation.
The exact-PID event audit finds no native crash for BD/BE/BF/BG. All four owned
CAD/debuggers exited and protected42248/46576 creation identities are unchanged.
This repetition confirms a rollback/restoration-sensitive model-state change;
it still does not reproduce the original CloseDoc exception.

## Earlier bounded controls and blocker audit

BH PID11784 restores the immutable prototype and accesses/releases ONLY the
rear-standard pattern, without reading seeds, changing a property or explicitly
rebuilding. Enumeration changes6→7 and adds beam9. CloseAllDocuments and normal
ExitApp succeed. This isolates a sufficient trigger for the observed component
regeneration, not a trigger for the original native crash.

BI PID48172 removes both the debugger and SOLIDWORKS_SCRIPT_TRACE_DIR. One fresh
MCP process opens the private prototype and runs the original pattern-refresh
script; that MCP process exits. A second fresh MCP process connects to the same
owned CAD PID, saves/copies/closes the assembly and exits the empty application.
Save3 is True/0/0 and CloseDoc succeeds. Per-phase server logs and the submitted
scripts/results are in `report-bi-uninstrumented.json`. Current server code
confirms line tracing is enabled only when its environment directory is set.
Thus debugger attachment, line-trace timing and retaining the first MCP process
do not suffice to explain why the previous controls did not crash in this state.
This does not reproduce all prior session history or exclude every timing race.

Exact-PID Windows event audit finds no event1000 for BH/BI. Both owned CAD
processes exited and no owned debugger remains. Protected42248/46576 retain
their original creation identities. No production model or other session was
operated. No production hook was introduced to regenerate patterns on close.

The completion audit still fails for40588 and other unassigned historical
signatures: a native failure is observed, but its first corrupting operation is
not established and no verified prevention for that particular failure exists.
The missing crash-time exception dump and contemporaneous dependency/process
state were established in the initial current-close investigation, persisted
through the paired-pattern continuation, and remain missing in this continuation
(at least three consecutive goal turns). Each earlier turn made progress through
bounded private controls; the new sufficient regeneration trigger and reduced
instrumentation controls now complete that planned matrix without a native
failure. Continuing to rearrange the same incomplete snapshot cannot prove the
original corruption mechanism. The agent is now at an evidentiary impasse for
this remaining requirement, rather than claiming the goal complete from the
three separately validated native paths.

Meaningful resumption requires an actual failing owned replay with exception
context, a usable original dump, or the missing crash-time input/process state
that makes a new faithful control possible. Without one of these, the root-cause
goal should be blocked, not endlessly extended with passing variants or a
speculative production fix. Retained input hashes, probes, failed/passing
results and known validated workarounds remain available for resumption.

Local repeatable runners: `run_az_resume.py`, `run_ba.py`, `run_bb.py`, `run_bc.py`;
reports and debugger/script traces are under ignored
`test-results/remaining-fault-correlation/`. `frozen-private-fixture` and its
file hash manifest retain the private clone. The opt-in recipes deliberately
do not publish user CAD bytes or start/attach to another session's instance.

## Investigation resumed with older retained history (2026-10-15)

The preceding evidentiary impasse is superseded by a newly located input and
same-PID history, not by interpreting another passing saved-state test as a fix.
`generic-before-front-rear.SLDASM`, saved at18:17:42, predates the previously
replayed18:30 input. Its preserved SHA256 is
`04a5adffed82d90a39f0515a8f2466958eec84d463e7486f2691d6d59ab9cc3a`.
The original logs retain18 calls from18:17 through18:36 for40588. Among the
newly included operations are front/rear mate creation, live equation deletion
and re-addition, rear-height equation repair, and first-floor pattern creation.
The18:34:59 call accesses pattern selections and then fails while casting a
returned seed to IComponent2, without ModifyDefinition or ReleaseSelectionAccess.
This failure was omitted from the earlier shortened controls.

This is a real API-contract problem: SOLIDWORKS documents that selection access
puts a feature into rollback and requires ModifyDefinition after modification,
or ReleaseSelectionAccess when it is not modified. The retained selection_scope
helper covers ordinary diagnostic exceptions. The missing release is a candidate
history difference, not yet proof of the original native corruption:
[official selection lifecycle](https://help.solidworks.com/2023/English/api/sldworksapiprogguide/Miscellaneous/Accessing_Selections_that_Define_Features.htm).

BX PID38148 starts from this older root with frozen private dependencies, checks
closed references and all loaded paths, and replays requests0..11. The original
rear equation Status=-1 and its subsequent repair are reproduced. However,
request12's dynamic matrix passes all cases whereas the original failed after
the second case. The harness stops with an explicit fidelity mismatch; it does
not silently continue toward the failed selection request15. Dependency bytes
are frozen and hash-checked, but are not proven identical to all crash-time
dependencies. BX must therefore not be called an exact40588 replay.

The subsequent private-only normal CloseAllDocuments attempt DOES reproduce a
native server fault. `report-bx-close.json` records RPC_E_SERVERFAULT, and the
owned exception watcher captures a2,134,660-byte exception dump before any
further CAD operation. Its debugger exception record is c0000005, an invalid
read at0x100000007 in dcu3d59!DCM3_node::do_move_to_list+0x83. The stack proceeds
through mfc140u, sldapiu, moFeature destruction, moMateWalker destruction and
iApiCloseDoc. Live .ecxr could not retrieve exception context. A subsequent
offline inspection DOES successfully load .ecxr from the preserved dump:
RIP matches the exception address, RBP is0xFFFFFFFF, and the failing instruction
`mov rax,qword ptr [rbp+8]` reads0x100000007. The independent exception-stream
parser records matching RIP and AMD64 control flags in exception-record.json;
offline-context.txt retains the debugger's registers/disassembly/stack. This
establishes the invalid node pointer at destruction, not its earlier writer.
This failing prefix precedes request15: unbalanced selection access is not a
necessary condition for THIS reproduced close failure. The address/signature
is not identical to40588's original Windows event, so common mechanism remains
to be demonstrated through reduced red/green controls.

No Save/Close/ExitApp retry was issued after the server fault. The preserved
dump and session creation identity were verified before terminating only the
faulted owned process via its held process handle. This cleanup is an explicit
test action, not a spontaneous application exit. BX's immutable source hashes
remain unchanged.

BZ PID16816 restores identical immutable sources, ends after request9, saves
and copies the root, then runs the original single-document CloseDoc. It again
returns RPC_E_SERVERFAULT, with a2,055,042-byte exception dump: c0000005 at the
same dcu3d59 address and the same invalid read0x100000007. Thus neither the
first-floor pattern build, the subsequent dynamic matrix, nor the failed
selection access is necessary for the reproduced failure. The closed document
is the root assembly; this is not only a failure while closing a different
child during BX's batch cleanup. No further CAD call follows the failure.
The preserved dump and exact process identity are verified before handle-based
cleanup of only16816.

Trace memory immediately before closing is87.32% commit for BX and91.84% for
BZ; both have available physical memory and no active recovery worker. This
does not prove resource pressure has no influence. `bx-bz-native-comparison.json`
retains exact snapshots, call attribution and equal immutable source hashes.
CB PID37172 is a fresh one-change prevention candidate: keep the same prefix,
replace request9's delete/re-add repair with refresh_existing_equation, then
require the original six-case independent-control matrix, save and CloseDoc.
The update preserves the equation at index11, valid Status11/value217.043 and
unchanged equation count/text/order. All six dynamic cases and Save3 pass.
CloseDoc STILL returns RPC_E_SERVERFAULT. Its2,154,779-byte exception dump has
c0000005 at mfc140u+0x23dc91, invalid read0x1, with matching stored exception RIP.
Thus the46576 in-place workaround is NOT sufficient prevention for this path.
Do not recommend it as a verified40588 fix. Exact process/dump identity is
preserved before faulted-process cleanup; no CAD call is retried afterward.

CB's dynamic operation stalls on a visible low-memory task dialog in its owned
PID during a beam-length property change. The trace stops at that Set2 line and
CPU activity subsides; the dialog text contains rm_commitcharge with Yes/No.
It later disappears and all six cases finish. Both separate cancellation
watchers report no matched events, so this investigation cannot claim either
watcher closed it. Its disappearance's actor is unknown. The resource delay is
not misreported as a native fault, nor does it erase the later captured CloseDoc
fault. This test does not exclude a memory-pressure contribution. The production
memory-warning handler is scoped to open_document; raw execute_python currently
has no equivalent explicit action scope around property changes.

CA is the next fresh control, stopping at request4, before distance-mate flipping
and before the rear equation repair. The prepared CC full-flow candidate is not
launched after CB disproved the proposed prevention. New tests use fresh frozen
sources; they do not retry the partially modified faulted process.

Local evidence: `current-close-40588/earlier-history/manifest.json`,
`40588-1817-1839-requests.json`, `40588-full-retained-api-history.json`,
`returned-error-audit.json`, `report-bx.json`, `report-bx-close.json`,
`debug-bx-close/exception.dmp`, and `current-close-40588/bx-faulted-cleanup.json`.
The retained85 PID-tagged reports contain no earlier native/RPC fault before
the18:39 report; absent/unrecorded calls are not excluded by that audit.
