# Native rear-mate lifetime regression — 2026-10-15

The failure now has a named native feature and an observed freed allocation.
Successful geometry/save/close tests alone are insufficient to certify this
native lifetime defect fixed. The investigation remains active.

## Confirmed RED state

CN's validated full exception dump establishes:

- Busy native moFeature_c0x56e78db0, named `後側_安裝高度` through three
  independent Memory64List string paths.
- Its+0x170 member points to0xee4f8cf0. Matching NTDLL heap types classify
  that target as LFH/free, entry size0x140, while the feature is LFH/busy.
- Native feature destruction passes that member to an API runtime-type query.
  MFC dispatch follows its residual DCM3_node vtable, enters do_move_to_list,
  and faults reading0x100000007. See CN_FULL_DUMP_NATIVE_DISPATCH.md.

CQ restores the same seven immutable inputs and15 CN CAD request ASTs. It
adds two between-request CDB /ma snapshots, each validated against the held
owned PID/start identity and full-memory bounds, then detaches/resumes. The
native exception watcher attaches before the original CloseDoc sequence.
Pausing/reattaching changes timing and is retained as an instrumentation limit.

| CQ checkpoint | Native mate | Member+0x170 | Actual heap state |
| --- | --- | --- | --- |
| After original direction-edit/rebuild/save request05 |0x2b3aaf90, moMateDistanceDim_c |0x1387fb8b0 | Feature LFH/busy, target LFH/free,size0x140 |
| After original request06's first property/equation/rebuild attempt | Same0x2b3aaf90 | Same0x1387fb8b0 | Still feature busy/target free |

Independent caption/name paths identify both snapshots' object as
`後側_安裝高度 (支架<1>,橫樑<3>)`. The target's residual table remains an API
command-target table in this trial. A second mate object with the same caption
has a null+0x170 member in both snapshots; its ownership/history relationship
has not been assigned merely from the duplicate caption.

CQ reproduces equation51 and nevertheless completes save/root close/batch
close/ExitApp. This demonstrates that a pass on close can coexist with the
retained free reference. It narrows the invalid lifetime to at or before the
request05 boundary; request06 and CloseDoc are not necessary to create this
observed stale reference. It does not yet prove request05 is the first creator.

Snapshot SHA256:

- after05:2bd36d4fe58006b44b561b249d6cb000be169b4c67a0d84a28cf8abf76719284
- after06:668aa850a6c942594541dc0fe7c10e89d97f7b6f26faaec71675f51c3e360369

## Green criteria and current test

CO's full staged construction and CP's independent saved/cold acceptance pass
physical, configuration, count, constraint, save and close checks. They do not
yet prove elimination of the native stale pointer. The existing equation helper
remains a verified functional binding workaround, without a universal native
lifetime-cure claim.

CR uses all22 CO CAD request ASTs unchanged, with three snapshots:

1. Before the original direction edit (after original request04).
2. After direction edit/rebuild/save, before binding refresh.
3. After the exact passing early binding refresh, before dynamic evaluation.

For the same independently named feature objects, compare native allocation
state, member identity and referenced allocation/type. A busy feature pointing
to a free/reused incompatible object remains RED even if later close succeeds.
A null member or a valid allocation must also be interpreted with the feature's
state/type and reference provenance; do not declare all native references safe
from one cleared field.

## CR result: functional pass, native lifetime still RED

CR completed all22 original CO CAD requests, both six-case matrices, the five
independent first-floor cases, save/root close/batch close/normal ExitApp. Seven
immutable inputs and all recorded production runtime hashes still match. Owned
PID21300 exited; there is no matching Windows event1000 (the same audit finds
the known CG/CN crash events). The native watcher produced no exception dump.

The three independent native snapshots give a narrower, different verdict:

| CR checkpoint | Matched native feature | Member+0x170 | Heap evidence |
| --- | --- | --- | --- |
| Before request05 |0x5610ab80, moMateDistanceDim_c | Null | Feature LFH/busy |
| After request05 | Original0x5610ab80 still null; additional0x5610a160 with the same independently matched name/caption |0x1334798d0 on the additional object | Additional feature LFH/busy, API target LFH/free,size0x140 |
| After early equation refresh | Both objects remain; additional0x5610a160 unchanged | Same0x1334798d0 | Still feature busy/API target free |

The freed target retains auCmdTarget_c RTTI and its CCmdTarget/CObject base
hierarchy. That residual type does not make a free allocation valid. This
disproves the stronger claim that the passing early equation refresh eliminates
this native lifetime defect. It repairs equation binding and passes functional
checks, but the invalid reference survives.

The first observed creation is now within request05: its GetDefinition,
FlipDimension update, ModifyDefinition, rebuild/save and Python request cleanup.
The snapshot before that request has no non-null+0x170 on the independently
matched object; the snapshot after it has the additional busy object with a
free API target. This does not identify an individual first-free instruction,
assign undo/history ownership to the duplicate object, or prove every native
reference safe before05. A finer boundary test is required before certifying
a preventive native lifetime fix.

CR snapshot SHA256:

- before05:f34f000a815c5efea7f69e9c1e0e0e926f41a854ce276f1eca45c63d819a62fe
- after05:fe831506a33ac76013c761e1fd83adbdfb8bfee84f7e62289da96b28a9373900
- after_refresh:5afe53eaab568c1f1799ffdca7400afd00b7362e77c59ced735bf9af93607b14

Actual saved-file predicates `verify_cq_native_reference_red.py` and
`verify_cr_native_reference_red.py` both pass their RED-evidence assertions;
their JSON results are in `current-close-40588/`. The CQ verifier initially
failed reading its UTF-8 report with Windows' cp950 default. Explicit UTF-8
fixes that local analysis issue; it did not change or rerun CAD requests.

The native watcher is delayed until after the checkpoints. A prefix native
failure would lack this trial's exception-time capture; such a failure must
stop CAD calls and be handled separately, not silently replayed.

## Retained reproducible tools

Under ignored `test-results/remaining-fault-correlation/`:

- `find_rear_mate_in_dump.py` independently locates the known CN object and
  each checkpoint object using both native name and caption pointer paths.
- `verify_cn_native_uaf.py` checks the actual member/heap/name/dispatch outputs.
- `snapshot_owned_checkpoint.py` permits only exact CQ/CR chat-owned manifests,
  checks executable/PID/start while holding a process handle, validates disk
  headroom, captures with CDB, verifies full memory bounds/PID/time, hashes the
  file and verifies the same live identity after detach. It invokes no CAD API.
- `analyze_cq_checkpoints.py` runs the saved-file object/heap inspections only.
- `run_cq.py`, `run_cr.py`, immutable manifests, debugger commands/stdout,
  checkpoint results, `rear-mate-object.json` and offline heap logs preserve
  the actual recipe and results. Original files are not renamed to hide errors.

No allocation/free stack trace was active before CN's original failure. These
tests seek the invalidating operation without modifying native CAD memory,
patching binaries or operating another chat's process.

## Finer operation boundary: CS

CS uses a fresh owned process and the same seven verified source snapshots.
Twenty-one requests remain byte/AST identical to CR. Request05 is split after
its successful ModifyDefinition, before its first explicit EditRebuild3,
ForceRebuild3 or Save3. A full-memory checkpoint runs after that first request
returns (including request-local wrapper cleanup). The continuation reacquires
the private document/assembly wrappers, then retains the original rebuild,
transform and save assertions. This intentional boundary changes lifetime and
timing; it is recorded rather than represented as an identical-request replay.

The complete CO/CR dynamics/first-floor/save/close workflow still follows. Native
exception watching starts after the checkpoint; a prefix fault must stop CAD
calls and receive separate handling. The gate requires6GiB available physical
memory and6GiB commit reserve for three samples before launching. One snapshot
is budgeted with separate disk headroom; existing dumps are retained.

The saved-file verifier compares both six-case and five-case geometry to CR,
verifies source/runtime hashes, and reports the actual named-feature heap
predicate separately from functional close success.

CS's checkpoint has now completed and been independently inspected. Owned
PID40736/start2026-10-15T06:28:23.674000Z remains the same live process after
debugger detach. The full3581112047-byte dump has6137 Memory64 ranges and
SHA25642029e0a421a88ad905ab2fe1a92899593aedf08a73764740c4779fd58d06584.
Independent native name/caption paths identify one busy moMateDistanceDim_c,
0x4e6ad680, whose+0x170 member is null. No retained-free API reference is
observed on this matched object at this boundary.

This differs from CR's post-rebuild/save boundary. It narrows the remaining
question to explicit rebuild/save or the lifetime/order difference introduced
by releasing request-local wrappers before rebuild. It does not prove the
invalid state absent after CS's later rebuild or establish a preventive fix.
`inspect_cs_modify_boundary.py` checks the actual dump SHA/native heap rows
and explicitly leaves post-rebuild state unverified.

CS has now completed all23 requests: both six-case dynamic calls, five
first-floor cases, save/root CloseDoc/batch close/ExitApp. A separate artifact
comparison verifies the persisted six-case and five-case geometry against CR,
including actual positions/counts/pattern flags/configurations/constraint states
within0.00001mm. All immutable source and production runtime hashes match.
Owned PID40736 exited normally; the event audit finds zero matching event1000
while still finding CG/CN's known failures. No exception dump was created.
Post-rebuild native allocation state remains uninspected in this trial; close
success must not be used to fill that gap.

The first comparison attempt reported a pattern-flag mismatch because it
compared GetComponents enumeration order. The saved evidence shows the same
fixed/arrayed frames in reversed enumeration order, at exactly the same two
positions. Sorting component records by actual position before comparing all
their attributes corrects the comparator; it does not drop the pattern flag
assertion, alter geometry, or rerun CAD requests. Full orientations and names
remain outside this comparison's stated scope.

Preparation initially failed in a local AST comparator because a formatted
request string is not a literal. The corrected comparator compares complete
request ASTs, verifies the21 unchanged requests, and reuses only hash-matching
unlaunched private inputs. No CAD had launched during that preparation error.

The official2023 [IDistanceMateFeatureData instructions](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDistanceMateFeatureData.html?id=2.2.1.105)
describe GetDefinition, cast, change data, then ModifyDefinition for distance
mate editing. That documented sequence does not establish correct native
lifetime in this observed model/runtime, nor does it identify the first free
instruction. Do not add AccessSelections based on unrelated feature interfaces.

## Post-rebuild verification preparation: CT

CT is prepared to preserve all23 CS CAD request ASTs exactly, changing only
the two between-request snapshot locations: after the split continuation's
rebuild/save, and after its early equation refresh. Native exception watching
begins after both snapshots, before the complete dynamics/first-floor/close
acceptance. Both snapshots must classify the actual matched native objects;
functional pass alone remains insufficient. Preparation is not a test result.
CT has passed its three-sample memory gate and launched owned PID50708 at
2026-10-15T06:42:34.734000Z. Its worker PID11932/start06:42:23.317000Z and
resource-gate state identify this single run. Native snapshots and full
acceptance are pending; no production Python source was changed for this test.

To retain disk headroom for these two full snapshots and a possible exception
dump, all three completed CR full dumps have been archived losslessly. The archiver
requires CS's verified normal finish and absent exact owned process before
starting; it checks the original SHA, streams ZIP compression/decompression,
and compares the decompressed full-byte SHA before removing only the duplicate
loose file. Each archive receipt retains original path, bytes, SHA and ZIP SHA.
All native evidence remains recoverable. `restore_cr_checkpoint.py <label>`
restores the exact checked bytes for the existing offline analysis tools and
keeps the archive. An actual before05 restore was executed and its full-file
SHA verified, then the loose duplicate was re-archived/removed only after the
same verified archive read. The three ZIPs total3235422436 bytes rather than
10657183659 loose bytes, freeing7421761223 bytes. Archive SHA receipts remain
beside each snapshot's original result and offline heap analysis. No fault-time
dump is deleted or rewritten. Disk free was17452769280 bytes before CT preparation.
