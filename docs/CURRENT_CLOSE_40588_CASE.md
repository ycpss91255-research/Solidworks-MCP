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

Local repeatable runners: `run_az_resume.py`, `run_ba.py`, `run_bb.py`, `run_bc.py`;
reports and debugger/script traces are under ignored
`test-results/remaining-fault-correlation/`. `frozen-private-fixture` and its
file hash manifest retain the private clone. The opt-in recipes deliberately
do not publish user CAD bytes or start/attach to another session's instance.
