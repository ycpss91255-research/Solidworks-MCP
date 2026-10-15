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
from one cleared field. CR's memory result is pending; preparation/launch is
not a green result.

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
