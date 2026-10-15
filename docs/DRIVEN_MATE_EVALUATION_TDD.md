# Driven distance-mate evaluation order: native regression investigation

Status2026-10-15: a reduced red/green native comparison is established. An atomic
composition subsequently failed native close and was removed. The exact passing
staged recipe, complete construction and saved-state acceptance are still being
verified. This document does not mark the broader crash goal done.

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

CJ now restores the exact passing CH two-call staging, including its original
rebuild/save checkpoint and fresh manager acquisition. It also runs the full
first-floor build, both six-case matrices and the five-case first-floor matrix.
Separate cold acceptance of the saved construction remains required. These
results are pending, not represented by CH's narrower passing prefix. The failed
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
