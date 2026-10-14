# Configuration crash regression: retained acceptance plan

This plan covers the reproduced old rack fixture's combined horizontal rebuild,
invalid diagonal switch and native close failure. It does not claim every
historical crash has been solved. No production model is modified by these tests.

## Current evidence and gates

| Gate | Current state | Evidence / next required test |
| --- | --- | --- |
| Original failing flow reproducible | Red established | AG/AH/AL, error61704 then native purecall/abort at close |
| Exception context available | Complete | AM close exception.dmp: `.exr -1` and `.ecxr` work, c0000409 subcode7 and native equation/model-update → document-close frames |
| Configuration recreation alone is enough | Disproved | AM recreates inactive configuration, restores inputs, keeps equations; still61704 and native close failure |
| Rebuild equations and references | Preserved-equation candidate passes static geometry | AQ fresh frozen input;29→18 equations; inactive configuration created with valid working equations intact |
| Fresh-input static repair | Passed AQ | AO's earlier error51 candidate failed; AQ changes the creation order and passes actual geometry |
| Acceptance rejects false green | Seven unit tests pass | Includes correct dimensions with error51, missing solid body, stale physical hole span, and correct IPartDoc feature lookup |
| Actual private-fixture regression | Passed AQ/AR | Both configurations rebuild with no feature/equation errors and correct physical hole spans |
| Save/close/reopen and physical geometry | Passed AQ and AT | All three Save3 calls True/0/0; geometry reverified after reopening |
| Dynamic assembly behavior retained | Passed AT for tested input | Parent binding restored; maximum segment height800→700→800; physical diagonal span1312.097557→1221.147002→1312.097557; horizontal unchanged |
| Cold separate-instance verification | Passed static AR; dynamic recipe check follows | Separate process opens saved fixture, verifies both configurations, closes and exits |
| Native crash-event audit | AQ/AR passed; later runs require audit | Exact interval Windows events1000/1001 empty; owned processes exited and protected identities unchanged |

## Retained test code

`tests/test_configuration_acceptance.py` was written before its implementation
and initially failed to import the missing diagnostic module. After implementing
the gates it has six passing tests. These are tests of acceptance logic, **not
proof that the CAD model is fixed**. Latest full unit-suite count is recorded
with the current iteration below.

`solidworks_mcp/diagnostics/configuration_acceptance.py` collects through an
already bound PID only. It never launches, opens, rebuilds, saves or closes CAD.
The caller supplies the actual preceding rebuild result. It checks private
loaded paths, current configuration, feature/equation errors, solid-body count,
dimension length and BRep cylinder-center hole span. Failed rebuilds skip the
physical-hole traversal and remain red. It uses no generic COM activation.

`tests/live_configuration_regression.py` is an opt-in, SOLIDWORKS2023/private
rack-fixture runner. It connects via a fresh MCP process to the selected existing
owned PID, uses `memory_warning_action=cancel`, and stops on the first failed
tool/acceptance result. It never launches another CAD instance or retries with
an alternate binding. By default it checks without saving. `--roundtrip`
explicitly saves only the private copies, closes, reopens through MCP with the
same cancellation policy, verifies both configurations again, and closes.
It does not exit or force-terminate the application; cleanup is a separate owned
session action. Native-event and cold-instance audits remain separate gates.

Run from this repository:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_configuration_acceptance.py
.\.venv\Scripts\python.exe tests/live_configuration_regression.py --manifest C:/absolute/private-fixture/configuration-case.json
.\.venv\Scripts\python.exe tests/live_configuration_regression.py --manifest C:/absolute/private-fixture/configuration-case.json --roundtrip
```

The manifest must explicitly name `fixture_dir`, `session_file`, `pid`,
`protected_pids`, `source_hashes`, and `expected`. Session PID/creation identity
must match the guarded launcher's file. Original sources must be outside the
private fixture; every loaded CAD document must be inside it. For this fixture,
the default expected values are:

```json
{
  "expected": {
    "橫撐": {"configuration":"橫撐", "length_mm":1070.0, "hole_span_mm":1040.0, "equation_count":18},
    "斜撐": {"configuration":"斜撐", "length_mm":1332.097557, "hole_span_mm":1312.097557, "equation_count":18}
  }
}
```

The local ignored `rack-before-config-repair/configuration-case.json` is the
complete case manifest. Its PID must be refreshed from a newly authorized owned
session before another run; stale session files do not authorize a new launch.
Original model hashes are in `CONFIRMED_CONFIGURATION_FATAL_EXIT.md`.
Private bytes/dumps are intentionally not committed.

Each runner report records phase, submitted code, result, timestamps, expected
values, runner/acceptance SHA256, original-source hashes and protected/target
process identities. Native observations are saved separately before assertions.
This preserves evidence when code changes later. A timeout is incomplete evidence;
inspect the same running handle. A memory cancellation is a deferred gate, not
the targeted configuration regression and never a successful open.

## Next iteration

### 2026-10-14 equation-preserving candidate

`tests/configuration_repair_candidate.py` provides an explicitly experimental
`apply_candidate(sw, interfaces, fixture_dir, expected_pid, diagonal_properties)`
for invocation through an already connected owned PID-bound MCP. It never
connects or launches, saves, rebuilds, closes, or verifies geometry itself.
It checks PID and private loaded-document paths before mutation. The archived
parameter JSON's `斜撐` object supplies `diagonal_properties`.

The candidate removes only obsolete helper equations and rewrites instance
aliases before creating the inactive configuration. Working dimension equations
remain present at configuration creation. Full equation replacement happens
only after both configurations exist. Three ordering/isolation regressions
were written first (missing-module RED), implemented, and passed GREEN.

Live AP exposed two test-harness faults: checking the Boolean return of an
already-active configuration switch, and calling FeatureByName on IModelDoc2
instead of IPartDoc. The latter now has a dedicated RED/GREEN regression.
AP's subsequent geometry acceptance passed and the owned process exited normally.

AQ restored all three original frozen files, applied the candidate, verified
both configurations using physical hole geometry, saved all three files with
Save3 `(True, 0, 0)`, closed, reopened, verified both again, closed and exited.
The expected spans were 1040.0 and 1312.097557 mm. No feature/equation errors
were observed. Original source hashes were preserved. Local reports are
`test-results/remaining-fault-correlation/report-aq.json` and private
`ap-observation-*.json`; CAD bytes and debugger dumps remain uncommitted.

This is evidence for the preserved-equation order on this fixture, not complete
production acceptance. The diagonal driver remains a temporary constant in
the experimental candidate. Parent-assembly binding, changed-input geometry
and restored baseline are still required before deploying a repair to real
models. Never replace the production workflow with this candidate merely
because the static geometry test passes.

Unit regressions including the new interface test: **243 passed**.

AR launched a separate owned process, opened AQ's saved private assembly without
applying another repair, verified both physical geometries, closed and exited
normally. This cold-instance gate passed (`report-ar.json`). The remaining
gates are dynamic parent binding and changed-input/restored-baseline behavior.

### Dynamic parent binding iteration

AS restores the parent equations and binds the diagonal dimension in assembly
EditPart2 context. The frame rebuild and both physical geometry checks pass.
AT repeats this on AQ's saved private fixture, changes the original parent
`驅動最大段高` property from800 to700 and restores800. Independent expectations
use `3200 / ceil(3200 / maximum)` and `hypot(1040, segment_height)`; actual hole
geometry must match. All four observations pass. The700 case has diagonal
length1241.147001798mm and hole span1221.147002mm, with horizontal geometry
unchanged. Save/close/reopen verifies the restored baseline and exits normally.

Retained code: `tests/configuration_dynamic_recipe.py` exposes `restore_binding`
and `verify_changed_input`. Both require an already bound app, typed interfaces,
absolute private fixture and explicit matching PID. No launch/save/close is
implicit. EditPart2 is left in a finally block. Input restoration uses a finally
block; a failed run still needs an explicit baseline rebuild and verification
before any save. The recipes assume this archived rack fixture and its inputs;
they are not a general geometry repair tool. Wrong-PID and non-private-document
regressions were RED before the module existed and now pass. Full suite245 pass.

Invoke through this chat's owned PID-bound `execute_python` context:

```python
from tests.configuration_dynamic_recipe import restore_binding, verify_changed_input
# sw and types must come from the already connected owned MCP and its installed typelib.
restore_binding(sw, types, absolute_private_fixture, explicit_owned_pid)
verify_changed_input(sw, types, absolute_private_fixture, explicit_owned_pid)
```

The comprehensive final gate must also verify assembly component placements and
pattern counts after the input change, then run the retained candidate and binding
recipe together from frozen original bytes. Static AQ and dynamic AT are separate
controls and must not be mislabeled as that single fresh-input combined run.

AU verifies the retained dynamic recipe in another owned cold process, including
700/800 physical geometry, baseline Save3/close/reopen and normal exit request.
AS/AT/AU had no new Windows application crash events in the audited interval.
Their source snapshots remain unchanged. Reports are `report-as.json`,
`report-at.json`, `report-au.json` and `as-at-au-event-audit.json` under the
ignored evidence directory. The launcher printed an IUnknown release warning
for AS, but exited successfully; fresh MCP connection and model tests succeeded.
This Python COM-release warning is not counted as a SolidWorks process crash.

### Full original-input assembly gate (AV/AW)

AV restored frozen original bytes and ran configuration repair plus parent
binding without the intermediate saved checkpoint used by AQ→AT. Its physical
part dimensions pass, but assembly enumeration reveals only one active diagonal
at800 and two at700: the three old pattern members remain suppressed. This
disproves treating the earlier geometry-only checks as full assembly acceptance.
The test stops before saving. It is a model-state failure, not a native crash.

The retained binding recipe now re-resolves each existing private diagonal
occurrence, not only its seed. AW repeats the full frozen-input flow. Actual
diagonal counts5→4 and horizontal count2 pass; all original occurrence matrices
are restored within1e-8. Physical world-hole endpoints also satisfy640/800mm
vertical segment spacing and1040mm horizontal spans. This check uses physical
hole centers and the observed native transforms, not equation counts alone.

AW then fails saving the brace: Save3 `(False, 1, 0)`. Activating the part before
Save3 in a same-PID diagnostic retry does not fix it. No close/reopen gate is
claimed from AW. The unused owned instance is closed normally without saving.
AX is the next control: validate/save the recreated configuration checkpoint
first, then bind/update/restore assembly geometry and verify final save/reopen.
It must not be reported successful until its recorded result passes.

`configuration_assembly_acceptance.py` provides read-only occurrence collection,
explicit expected configuration counts, numeric restoration/roundtrip placement
comparison and physical brace-grid validation. Five acceptance regressions were
RED before the missing implementation and are now GREEN. A correct count with
wrong physical spacing remains a failure. This fixture's grid uses global Y for
height and Z for horizontal span; these axes are not a general CAD assumption.
The observed matrix convention follows the official
[IMathTransform API](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IMathTransform.html).

AX's complete frozen-input staged flow passes. Both configurations first rebuild
and pass physical geometry; all three private files save with True/0/0 at that
checkpoint. Binding restoration resolves the diagonal pattern members. Maximum
segment height700 then800 gives actual diagonal counts5 then4 and horizontal2;
the physical endpoint grid verifies640/800mm height increments and1040mm spans.
All eight baseline component transforms and suppression/configuration states
return to their original verified values. Final Save3 of all three documents is
True/0/0. Close/reopen verifies both physical geometries and all eight component
placements, then closes and requests normal ExitApp. Source hashes remain intact.

AW versus AX supports checkpoint-before-parent-binding as a workaround for this
fixture's Save3 error1. It does not prove the internal native reason for that
generic save error. Do not label error1 an access violation or a memory crash.
The retained final repair order is:

1. Restore immutable inputs into private files and rebind closed references.
2. Apply `apply_candidate`, preserving working equations at configuration creation.
3. Verify both configurations physically; explicitly Save3 each private document
   and require True/0/0. Stop on failure.
4. Run `restore_binding`, then `verify_changed_input` with the assembly-observer
   callback; require counts, physical endpoint layout and restored matrices.
5. Save all private files; close/reopen and verify dimensions plus occurrence
   state; close the empty owned instance normally.
6. Open the saved files in a separate owned process and verify geometry and all
   placements again; audit exact process exits and Windows crash events.

Latest full unit suite: **250 passed**. The five assembly acceptance regressions
and native collector are retained in `test_configuration_assembly_acceptance.py`
and `configuration_assembly_acceptance.py`. AX's reproducible local runner,
submitted code, trace and result are `run_ax.py`, `trace-ax/`, `report-ax.json`,
`ax-physical-grid-report.json` under the ignored evidence directory.

AY's separate-process geometry and all-eight-occurrence placement verification
also pass, followed by CloseAllDocuments/ExitApp. Final audit records no event1000
for owned test PIDs40096,316,44948,42900; all owned CAD/debuggers exited. A new
event for protected PID40588 is distinct and investigated read-only. Do not
claim the entire machine had no crash or that both other sessions stayed running:
40588 exited independently, while42248 remains. The exact new call correlation
is retained in ROOT_CAUSE_FINDINGS.md; it keeps the broader root-cause goal open.


1. Restore the frozen three-file input into the private fixture after owned CAD
   is closed. Keep a complete equation snapshot and archived parameter inputs.
2. Preserve working horizontal equations while creating the inactive diagonal
   configuration; then populate configuration-aware equations. The earlier
   prototype temporarily removed all equations before creating the configuration.
3. Inspect/fix the in-context sketch reference producing error51. Restore parent
   binding and retain the original dynamic behavior; do not suppress the failing
   feature or replace dynamics with a constant merely to pass a narrow test.
4. Run acceptance red/green, roundtrip, changed-input geometry, restored baseline,
   cold owned instance, and exact-PID native-event checks.
5. Publish the validated change and final evidence only after every gate passes.

During this turn, a95% commit reading was followed by an unnecessary empty test
launch; it was immediately closed normally without loading models. Subsequent
private launch attempts were gated on current headroom. This is a test-lab
resource precaution, not a machine-wide instance cap or change to other tasks.
