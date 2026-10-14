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
| Rebuild equations and references | Candidate only | AN resumed repair:29→18 equations, expected dimensions, save/close/exit pass; not a pristine single-pass control |
| Fresh-input complete repair | Failing | AO fresh control: switch succeeds, full rebuild fails; feature error51; in-context parent binding restoration still returns false |
| Acceptance rejects false green | Six unit tests pass | Correct dimensions with error51/failed rebuild, no solid body, wrong physical hole span, wrong configuration, equation failure, missing/nonfinite measurements all rejected |
| Actual private-fixture regression | Deferred | Latest live run cancelled by low-memory warning before geometry verification; not counted as repair success |
| Save/close/reopen and physical geometry | Pending | Both configurations must pass before and after `--roundtrip` |
| Dynamic assembly behavior retained | Pending | Restore parent-driven diagonal length; vary original inputs and verify physical holes/placements, then restore baseline |
| Cold separate-instance verification | Pending | Close owned empty instance normally, guarded launch with own session file, reopen saved private fixture, rerun geometry acceptance |
| Native crash-event audit | Pending for completed repair | Query Windows event1000 for exact test PID/time interval; successful tool return alone is insufficient |

## Retained test code

`tests/test_configuration_acceptance.py` was written before its implementation
and initially failed to import the missing diagnostic module. After implementing
the gates it has six passing tests. These are tests of acceptance logic, **not
proof that the CAD model is fixed**. Full unit suite:239 passing tests.

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
