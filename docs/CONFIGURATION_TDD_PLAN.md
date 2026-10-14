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
