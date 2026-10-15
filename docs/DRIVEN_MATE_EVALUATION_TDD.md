# Driven distance-mate evaluation order: native regression investigation

Status2026-10-15: a reduced red/green native comparison is established. An atomic
composition subsequently failed native close and was removed. The exact passing
staged recipe passes completed CJ continuation and CK cold acceptance. CL's
untraced/reconnected unrepaired control also closes. Fresh trace-on CM passes,
while same-runtime trace-off CN fails with the original native dispatch path;
tracing is not necessary. Fresh uninterrupted full staged replay CO passes;
saved/cold verification CP also passes, including independent physical and source/runtime
hash comparisons. CN's full dump proves a use-after-free for the rear installation-height
mate. CQ/CR prove that functional close PASS can coexist with a retained free
API reference, and CT records that same allocation reused as a DCM solver
object. CU's within-run snapshots are clear after both explicit rebuild calls;
the invalid reference first appears after transform observation/Save3. The
remaining observation-versus-save boundary is under test. These findings
supersede any interpretation that passing staged equation repair establishes
a native lifetime cure. See [NATIVE_REFERENCE_LIFETIME_TDD.md](NATIVE_REFERENCE_LIFETIME_TDD.md)
and [CJ_CK_CL_NATIVE_RESULTS.md](CJ_CK_CL_NATIVE_RESULTS.md).
This document does not mark the broader crash goal done.

## Reproduced failure interval

The older18:17 private input and retained40588 call history now reproduce native
faults that saved-state-only controls missed. Exact provenance, original event
limits and the larger matrix are in [CURRENT_CLOSE_40588_CASE.md](CURRENT_CLOSE_40588_CASE.md).
All trials use a fresh owned PID, frozen private sources, checked closed
references and loaded document paths, and SOLIDWORKS_RECOVERY_MONITOR=0.

- CA, original requests0..4: close succeeds, but rearY=-267.043mm is incorrect.
  This is only a close control and cannot be recommended as a functional fix.
- CD, add request5 FlipDimension/ModifyDefinition/rebuild/save: rearY becomes
  the required167.043mm; root CloseDoc and normal ExitApp succeed.
- CG, add only request6's initial property setting, EvaluateAll and rebuild:
  the first validation records Equations error51, then CloseDoc gives
  RPC_E_SERVERFAULT. Its exception dump records c0000005 in
  dcu3d59!DCM3_node::do_move_to_list+0x83, read0x100000007. Stored RIP matches.
- BZ includes the later delete/re-add repair and still fails native close.
- CB refreshes the existing equation in place AFTER the failed first evaluation.
  Binding and all six dynamic cases become valid, but CloseDoc still fails in
  mfc140u+0x23dc91. Later valid geometry does not restore the native process.
- CH moves that same in-place refresh BEFORE the first explicit equation
  evaluation. The six original dynamic cases, Save3, root CloseDoc, batch
  cleanup and normal ExitApp all succeed. The owned process/debugger exit,
  with no captured native AV. Immutable sources remain unchanged.

`early-binding-geometry-comparison.json` independently compares CB and CH with
the original six-case output saved18:28:05, SHA256
`253bc6ff991817db092370a98ad65f578f504d027b1fe3468fecece9c2ab10d7`.
Inputs, lengths, counts, positions within1e-5mm, pattern flags, configurations,
constraint status and empty feature-error lists match. Names and full rotation
matrices are not compared. Both match the observed geometry, but only CH closes
successfully. These tests preserve the intended physical requirements.

Close-time commit is90.68% for failing CG,93.93% for failing CB, and90.08% for
passing CH; CA also passes at90.48%. Thus high commit alone is not sufficient
for the observed fault. These are not proof that pressure has no influence.
CB's earlier low-memory dialog delay is recorded separately from its later
native fault; its disappearance was not attributed to an unverified action.

An independent Application Error event query from10:40 onward was correlated
using BOTH PID and process creation time, then checked against each stored dump:

| Trial | Owned PID | Event1000 record | Module and RVA | Comparison |
| --- | --- | --- | --- | --- |
| CB |37172|24299|mfc140u+0x23dc91|c0000005 and module offset match dump|
| CG |45452|24331|dcu3d59+0x11073|c0000005 and module offset match dump|
| CH |2900|none in queried interval|normal close and ExitApp|no event with this PID/start identity|
| CI |42480|24360|mfc140u+0x33d8b0|c0000005 and module offset match dump|

Local `current-close-40588/recent-native-event-correlation.json` retains the
query-derived records, creation identities, timestamps and dump hashes. This
independently confirms native CAD exceptions for these three failed controls;
it is not merely an inference from an MCP timeout or a later intentional cleanup.
The dump's own MiscInfo PID and process creation seconds also match each owned
session, independently of the debugger sidecar and Windows event. All three
captures pass the cleanup helper's read-only `--verify-only` path. Future fault
cleanup validates the actual exception/context, dump identity and hash before
opening a termination handle; a full capture additionally requires a bounded,
readable Memory64List payload. File existence alone is insufficient.

The original46576 event23224 (2026-10-14 20:28:51 Taipei) and CB event24299
also have identical recorded AppVersion/AppTimeStamp, MFC ModuleVersion
14.50.35719.0/ModuleTimeStamp58bc9fe7, module path, c0000005 and fault offset
0x23dc91. `original-46576-cb-mfc-site-comparison.json` preserves that direct XML/
JSON comparison and both input hashes. The matching current public symbols put
this offset in `CObject::IsKindOf`; the original historical dump/registers are
still unavailable. Same recorded native site does not prove identical earlier
corruption, identical model state or byte identity of the historical DLL.

## Retained helper, failed composition and regression evidence

The retained API is still
`solidworks_mcp.equation_binding.refresh_existing_equation(manager,index,text)`.
The caller verifies owned PID, document identity, intended driving equation and
single configuration. Its five existing regressions cover unchanged formula/
order, no Delete/Add2, stale-input rejection, invalid binding, no follow-up after
native failure, and structural-change rejection. Current full discovery is273
passing tests after reverting the failed experiment below.

CH's passing recipe has TWO separate execute_python calls. First it runs the
original direction edit, EditRebuild3, ForceRebuild3 and Save3 checkpoint, then
that execution context returns. The next call reacquires the feature/dimension
and a fresh typed equation manager, and invokes refresh_existing_equation before
the original failed evaluation. Its own rebuild/save and six-case matrix follow.
That exact staging is the tested scope; it does not prove that rebuilding,
checkpoint saving, fresh manager acquisition or COM reference lifetimes can be
omitted or arbitrarily reordered.

CI PID42480 tried an atomic composed function with an equation manager acquired
before ModifyDefinition, rebinding before the original rebuild/save checkpoint.
Six new stateful fake tests went RED then GREEN, and full discovery reached279,
but its native six-case/save/CloseDoc test FAILED RPC_E_SERVERFAULT. The preserved
2,045,899-byte exception dump records c0000005 execute violation in mfc140u with
matching stored RIP. Thus the fake ordering model was incomplete. The unverified
function and its six tests were removed from production; their exact source is
archived locally with the failed trial. They are not advertised as a safe API or
as evidence that273 current tests verify the native staging problem.

Further offline CI inspection confirms what that execute violation means at
the failure point. Its captured MemoryInfoList region is MEM_COMMIT (0x1000),
MEM_IMAGE (0x1000000), Protect=PAGE_READONLY (0x2), in System32/mfc140u.dll at
RVA0x33d8b0. Exception parameter0 is8 (execution), stored RIP/target agree,
and the region has no execute permission. The caller at mfc140u+0x23dc91 loads
an indirect function target; its return address0x23dc9a also appears below the
DCM failures and the CB read failure. This narrows the common failure site to
invalid native object/dispatch state during feature/mate destruction. It does
NOT identify the earlier writer or distinguish use-after-free from another
invalid-object/lifetime defect, and does not exclude pressure as a contributor.

The dump's region was parsed directly according to
[MINIDUMP_MEMORY_INFO](https://learn.microsoft.com/en-us/windows/win32/api/minidumpapiset/ns-minidumpapiset-minidump_memory_info)
and [memory protection constants](https://learn.microsoft.com/en-us/windows/win32/memory/memory-protection-constants).
The independent offline .ecxr/register/disassembly/stack output is retained.
CDB !address itself could not proceed without ntdll type symbols; its failure
was not represented as a successful memory-map inspection. Local evidence:
`debug-ci-config-repair/exception-memory-region.json`, `offline-context.txt`
and `offline-dispatch.txt`, plus the exception dump and its SHA256 manifest.

Microsoft's matching public MFC symbols now identify mfc140u+0x23dc80 as
`CObject::IsKindOf(CRuntimeClass*)` and the CI execute target, +0x33d8b0, as
`CAfxStringMgr::vftable` (six entries). The successful lookup is preserved in
`public-mfc-symbols-native-path.txt`. The downloaded public PDB SHA256 is
`70aa5532c468f40ef0f42d3f4164a2e859b524f898b57ca657397e526f0d285e`.
The CObject type check is dispatching to string-manager vtable DATA rather than
an executable function entry. This is evidence of an invalid native object or
dispatch state at destruction, not proof of the API call that first caused it.
The small CI dump does not contain the object bytes at RCX=0x52cf9240;
`dq @rcx` cannot read them. Heap ownership, allocation history and an earlier
writer therefore cannot be inferred from this dump.
An independent bounded file reader checks actual MemoryList/Memory64List
coverage and confirms that missing RCX/argument coverage, while reading the
captured stack and fault-target data. Its output is
`exception-object-memory.json`. Dump readers and cleanup hashing now avoid
copying a future full dump into a single large Python bytes allocation.
Four local synthetic file-format checks pass: Memory64List object/vtable reads,
ordinary MemoryList offsets, missing object bytes remain unknown, and a
truncated full-memory payload is rejected without an output report. These are
diagnostic reader checks, separate from273 production unit tests and still not
evidence of a completed full-memory CAD replay.

For a future owned failing control, the local PID-bound capture script has an
opt-in `--full-memory` mode using [.dump /ma](https://learn.microsoft.com/en-us/windows-hardware/drivers/debuggercmds/-dump--create-dump-file-).
It checks free disk space against the current owned process footprint plus2GiB;
normal detach breakpoints retain the small format. This preparation is not a
claim that a full dump has yet been captured or that inaccessible pages will
be recoverable. While the existing continuation worker was confirmed still
waiting, its runner was atomically upgraded to request --full-memory, preserving
all CAD request ASTs and the same worker/PID/model state. The prior source and
explicit text/file hashes are retained in `cj-resume-capture-upgrade.json` and
`run_cj_resume_before_full_memory.py`. At actual attachment, verify
`debug-cj-resume/ready.json` reports exception_dump_option=/ma; the preparation
alone is not proof of the effective capture mode or a completed full dump.

CJ now restores the exact passing CH two-call staging, including its original
rebuild/save checkpoint and fresh manager acquisition. It also runs the full
first-floor build, both six-case matrices and the five-case first-floor matrix.
Separate cold acceptance of the saved construction remains required. These
results were initially pending; the completed CJ continuation and CK cold result
are documented below. Fresh single-MCP replay CO is still required. The failed
atomic variation is not silently retried on its faulted PID.

CJ's first six-case matrix completes. Its later diagnostic-only verification
then raises AttributeError because the harness uses IModelDoc2.FeatureByName
instead of the assembly interface. No native exception is captured. After
confirming that exact error, null HRESULT, unchanged sources, debugger detach
and the still-live PID37192 creation identity, a continuation corrects only
that lookup and resumes at that verification on the SAME private model/PID.
The failed report remains report-cj.json; continuation is report-cj-resume.json.
The resource worker waits for headroom before connecting, without replaying
the prefix, reopening a model or starting another CAD process. This local
harness failure is not counted as a native failure or a successful full test.

The mate-definition edit route is documented by SOLIDWORKS; this is not a reason
to ban all ModifyDefinition or FlipDimension calls:
[IDistanceMateFeatureData](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDistanceMateFeatureData.html).
Updating an existing equation uses the
[Equation property](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IEquationMgr~Equation.html).

## Attribution and evidence limits

The observed failing interval is evaluation/rebuild after the mate edit;
CH's fully staged early refresh passes and the simplified CI composition fails.
CG's combined request does not identify the exact first C++ write among property
setting/evaluation/rebuild. Rebinding order alone is not a sufficient general
explanation without the additional staging/lifetime controls.
That request also starts its check function with ActivateDoc3(path,False,0,0).
The official [ActivateDoc3 contract](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~ActivateDoc3.html)
and [activation rebuild enumeration](https://help.solidworks.com/2024/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swRebuildOnActivation_e.html)
define0 as user-decision/prompt,1 as no rebuild and2 as rebuild. Thus the
activation is not a documented no-rebuild operation. No prompt or implicit
rebuild in this particular request has been established. Any further prefix
reduction must account for activation and COM context acquisition as well as
Set2/EvaluateAll/EditRebuild3/ForceRebuild3 and later observation calls; CG/CD
alone cannot attribute the first corrupting operation specifically to EvaluateAll.
The original40588 exception dump and exact contemporaneous dependency identity
remain unavailable; matching intent and fresh failing history are not the same
as proving that original unknown-module instruction. Retain this distinction.

Native calls stop after each server fault. Dumps, PID creation identity and
executable are verified before faulted-process cleanup through its held handle.
That cleanup is explicit test termination, not spontaneous CAD exit. Passing
ExitApp is separately recorded after empty-document verification. Other session
PIDs, production files, registry/security settings and MCP connections are not
operated. There is no global instance cap or forced closure of other instances.

Local private evidence lives under ignored `test-results/remaining-fault-correlation/`:
`report-ca/cd/cg/cb/ch.json`, corresponding trace/debugger directories,
`current-close-40588/early-prefix-matrix.json`,
`early-binding-geometry-comparison.json`, frozen input hashes and cleanup records.
CAD bytes, crash dumps and private traces are deliberately not published.
