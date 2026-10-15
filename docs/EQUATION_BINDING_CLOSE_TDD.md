# Mate equation refresh and native close failure

This evidence concerns the received46576 case and its private owned replays on
SOLIDWORKS2023 SP5. It does not attribute every historical crash, including40588.

## Confirmed trigger and documented API restriction

The original request modifies three left-mate face references, traverses the
live equation manager with `reversed(range(e.GetCount()))`, deletes the existing
distance-mate equation and adds identical text, then deletes old child mates and
a component. Closing the documents subsequently faults in the native CAD process.
The same closing call fails in owned BM and fresh BP, with native exception dumps.

The SOLIDWORKS2023 [Delete documentation](https://help.solidworks.com/2023/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IEquationMgr~Delete.html)
explicitly warns against deletion while traversing the model's equations because
CAD may crash. [Add2](https://help.solidworks.com/2017/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.iequationmgr~add2.html)
has the corresponding addition warning. Reversing Python's index range does not
make this an API pattern supported by those remarks. These warnings support the
call-sequence diagnosis; they do not identify the first corrupting C++ write.

| Fresh control after mirror history | Close outcome |
| --- | --- |
| BO: mirror operations only | Pass |
| BQ: three mate references replaced, no equation recreation/deletion | Pass |
| BR: references replaced and old child deleted, no equation recreation | Pass |
| BS: references replaced and equation recreated, no child deletion | Pass |
| BP: replacements, equation recreation and child deletion together | Native server fault |

Thus the observed trigger is an interaction in this workflow, not proof that
each individual API always fails. Transport reports the native/RPC error; it is
not an ordinary MCP timeout, an intentional ExitApp or proof of a bad installation.
Owned recovery monitoring was disabled in these controls, so backup interaction
is not necessary for this reproduced path. This does not exclude all other
backup or memory effects in production.

## Red/green and preserved behavior

Simply omitting equation recreation is not a complete repair. BU's dynamic
acceptance rejects error51 on the Equations feature: row2 retains the text
`"D1@左端_安裝高度" = "前側安裝高度"` but has Status=-1 after the mate change.
Its unchanged-looking initial geometry is not sufficient evidence of validity.

An in-place property update of that same equation restores a valid binding
without Delete/Add2. The [Equation property](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IEquationMgr~Equation.html)
is the documented update API; configuration-specific equations require the
appropriate configuration-aware API instead.

`solidworks_mcp.equation_binding.refresh_existing_equation(manager,index,text)`
implements the update with exact index/text preflight, evaluation, valid-status/
finite-value checks and unchanged count/text/order verification. The pywin32
property setter normally returns None; it is not interpreted as an integer
success code. Native exceptions propagate without retry or another CAD call.
The caller owns PID/document/configuration preflight, rebuild and physical checks.
It does not launch/save/close or automatically rewrite arbitrary execute_python
requests, and does not claim to verify internal native object identity.

- Warm BU repair: restores the binding, passes all8 dynamic cases and Save3/
  batch close. Its immediate reopen is cancelled for a low-memory warning;
  that cancelled operation is not counted as cold acceptance. All partially
  loaded documents were verified private, closed and the process exited normally.
- Fresh BV, owned15976: restored frozen input, full mirror/rear-pattern flow,
  callable helper before child deletion,8 dynamic cases, successful saves,
  batch close and normal exit. Source hashes remain unchanged.
- Separate process BW, owned38848: saved BV files frozen/copied and references
  rebound privately; as-loaded physical baseline, changed height/spacing and
  restoration all pass, then save/batch-close/normal exit. Source hashes remain
  unchanged. Resource cancellation, if encountered, is inspected and cleaned
  before the same private open is retried after headroom recovers.
- All8 fresh observations and3 saved/cold observations match the original
  dimensions, counts, sorted positions, pattern flags and constraint status to
  1e-5mm. Component names and byte-identical JSON are not claimed.

The final event/process audit finds no event1000 for the successful BQ–BW owned
PIDs and no remaining owned CAD/debuggers. Faulted BM/BP were deliberately
terminated through identity-held handles after capture; that cleanup is not
misreported as spontaneous CAD termination. Other sessions were not operated.
The observed non-test inventory changed from1772/42248 to1772/44968; these controls
did not operate those PIDs or attribute that external transition. Do not claim
every other process remained continuously running.

## Retained regression evidence and limits

Five unit cases in `test_equation_binding.py` cover the None-returning setter,
no Delete/Add2, stale input rejection, invalid binding, native failure without
follow-up and changed equation order. Full discovery passes273 tests, including
resource waiting and process identity regressions. The live recipe deliberately
starts from immutable inputs and verifies full dynamics and saved geometry;
successful tool calls alone do not mark the broader goal complete.

Ignored local evidence under `test-results/remaining-fault-correlation/`:
`run_bv.py`, `run_bw_resume2.py`, `report-bv.json`, `report-bw-resume2.json`,
`trace-bv/`, `trace-bw-resume2/`, corresponding debugger directories and the
case's `bv-bw-physical-comparison.json`, `bq-bw-event-process-audit.json`, immutable
manifests and recorded resource transitions. The fixture source remains private.

The low-memory cancellation and local cold-harness setup failures are retained
separately from native CAD failures. The corrected queue checks a process handle's
signaled state as well as its creation identity: an exited Windows process object
can remain queryable. No old job is relaunched merely because observation times out.

This provides a reproduced trigger and tested workaround for this path. The exact
original46576 native address differs from the owned execute-at0x108 exceptions;
private vendor symbols/internal write provenance are not available. The distinct
40588 case remains unattributed. These limits keep the broader investigation open.
