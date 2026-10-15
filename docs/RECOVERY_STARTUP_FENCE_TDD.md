# Recovery worker startup fencing — TDD evidence, 2026-10-15

The isolated candidate passed 363 regression tests and actual SolidWorks
acceptance on an owned private part: worker startup/stop/retry, native-setting
automatic startup, a dirty-part recovery copy, and separate reopened 2 mm
baseline/3 mm backup geometry. The owned CAD process exited normally and its
watcher captured no native exception. It has **not been deployed**, and the actual
MR12 reservation has **not been changed**. This change does not establish a cause
for unexplained CAD exits.

## Observed defect and resulting behavior

MR12's `worker-startup.json` retained PID 2836 and its October 12 creation time
after the session moved to newer SolidWorks processes. There was no
`monitor.json`; the audited logs contained 172 startup-reservation mismatch
warnings. The old code rejected the reservation before launching its recovery
worker. That establishes a backup startup failure, not that backup caused a CAD
exit.

Simply removing that file is unsafe: a venv launcher can exit while its real
Python worker is still starting. The old worker also read the mutable session
file without an immutable target fence, so a delayed attempt could adopt a newer
target.

The candidate in [recovery_service.py](../solidworks_mcp/recovery_service.py) and
[recovery_monitor.py](../solidworks_mcp/recovery_monitor.py) adds:

- An explicit startup token plus expected CAD PID/creation time. The child checks
  reservation, session, OS identity and stop marker before constructing a backend.
- A short reconciliation/claim section under the session monitor mutex. The
  parent holds the separate launch mutex while waiting; the child never requests
  that mutex, avoiding a parent/child startup deadlock.
- Claimed worker PID, creation time and image metadata, and launcher metadata
  recorded before its suspended process resumes. A timeout alone is not proof
  that a worker died.
- Byte-preserving archival of proven terminal reservations/status under
  `retired-startups`, followed by a fresh token. Archive paths must remain inside
  the private recovery directory. Live, reused, inaccessible or ambiguous
  identities remain refusals.
- Retry after a proven pre-creation failure. For a known launcher that exits
  before claim, retry also requires a complete empty same-session worker scan
  under both locks; launcher exit alone is insufficient.

## Old-parent compatibility and legacy repair

An already-loaded old parent can still start a child with `--startup-token`
without the new expected-target arguments. The child obtains its expected
PID/creation time **from the matching reservation while holding the monitor
mutex**, checks it against both current session and OS identity, then upgrades
the reservation on claim. It does not derive a replacement target from the
current session. A wrong token, target, session or OS creation time prevents all
backend calls.

Normal connection does not silently erase an unconfirmed legacy reservation.
The explicit repair entry point is:

```powershell
python -m solidworks_mcp.recovery_service --retire-stale-startup `
  --session-file "C:\absolute\owned-session.json" `
  --directory "C:\absolute\owned-recovery-directory"
```

Run from the intended checkout with its Python environment and real absolute
paths. This command only archives verified stale metadata; it does not launch,
attach to, close or kill CAD. For owner-unknown legacy records it requires the
old target to be absent, a live verified current target, matching session
ownership, no stop marker and a complete empty worker inventory while both
session locks are held. Any uncertainty preserves the record. A subsequent
ordinary connection can attempt startup; the repair command itself is not
evidence that monitoring or backup now works.

[recovery_process_scan.py](../solidworks_mcp/recovery_process_scan.py) reads two
Windows process snapshots and holds candidate handles between them. It parses
the exact module/session arguments and accounts for both venv launcher and real
worker. Inaccessible metadata, a candidate disappearing, changed snapshots or
PID identity mismatch produce an explicit unknown result, not an empty list.
The actual MR12 directory was not passed to the repair command during these tests.

## Reproduced RED and verified GREEN

| Evidence | Verified result and boundary |
| --- | --- |
| [Frozen baseline replay](../test-results/recovery-reservation-fence/red-frozen-replay.json), [console](../test-results/recovery-reservation-fence/red-frozen-replay.txt) | Three named regressions fail against preserved commit `5793bcf17f0d8697a469b66c6e66cb4e854af04f` sources: dead stale claim retry, immediate launch-failure retry and expected-identity arguments. The report pins baseline/test SHA256 values. |
| [Preclaim-launcher RED](../test-results/recovery-reservation-fence/red-unclaimed-launcher.txt) | Preserves the later discovered failure where an exited launcher without a claim stranded the current target's attempt. |
| [Token-only RED](../test-results/recovery-reservation-fence/token-only-red.txt), [source](../test-results/recovery-reservation-fence/token-only-red-source.py), [tests](../test-results/recovery-reservation-fence/token-only-red-tests.py) | Preserves the incompatible intermediate child before the token-only compatibility fix. |
| [Final full-suite proof](../test-results/recovery-reservation-fence/final-green-v1.json), [console](../test-results/recovery-reservation-fence/final-green-v1-console.txt) | **363 tests passed in 21.262 seconds**. Root/package Python and discovered test files have matching SHA256 maps before/after the run; `git diff --check` returned 0. |
| [Scanner tests](../tests/test_recovery_process_scan.py) | 17 controls cover exact session, both process layers, unknown metadata, access denial, disappearance, PID reuse, ambiguous arguments and changed inventory. |
| [Windows startup tests](../tests/test_recovery_startup_windows.py) | Seven tests use fresh harmless Python children, real mutexes, files and worker identities. They exercise duplicate claims, parent/child lock ordering, a late old token, actual child exit and retry, real preclaim exit plus inventory, and old CLI `main` with a backend spy. The old-CLI case contains a positive arm and four zero-backend refusal arms. |
| [Real process inventory proof](../test-results/recovery-reservation-fence/recovery-process-scan-native-v2.json) | Under both session locks, an old-style tokenless target CLI fixture exposes both venv and real worker; exit during the actual snapshot is refused, then natural exits permit an empty result. No CAD backend is used. |
| [Real desktop callback proof](../test-results/recovery-reservation-fence/recovery-desktop-callback-native-v1.json) | The production desktop launcher writes metadata before its harmless child runs; the held launcher exits naturally with code 0. This is not a CAD launch. |

The two copied native Windows evidence files have verified provenance in
[native-evidence-provenance-v1.json](../test-results/recovery-reservation-fence/native-evidence-provenance-v1.json).

The final run used `python -m unittest discover -s tests -p "test_*.py" -v` from
this isolated checkout. These tests mock CAD and include Windows-specific helper
process checks; “full suite” does not mean platform-independent or native CAD
acceptance. Files named `verify_*.py`, including the prepared
[owned native harness](../tests/verify_owned_recovery_native.py), are deliberately
outside this discovery command.

## Actual native acceptance

The [native acceptance evidence](../test-results/recovery-reservation-fence/native-acceptance-v1.json)
pins each original receipt by absolute path and SHA256. The target was this
chat's private SolidWorks PID **24588**, creation time
`2026-10-15T11:45:58.673000+00:00`. No other chat's CAD was operated.

| Stage | Verified result |
| --- | --- |
| Worker lifecycle | Real isolated workers **35496** and **2216** each reached `waiting_clean`, received the owned stop marker, and exited naturally with code 0. The second attempt used a new startup token/creation identity, preserving the old monitor status. Lifecycle alone used explicit forced mode with a short interval. |
| Synthetic legacy repair | A new private session copy and a labelled synthetic legacy reservation used the first naturally exited worker as its old identity. The actual retirement API, real Windows scanner and mutexes preserved the reservation bytes in an archive without launching any worker or CAD. This did not touch MR12's real reservation. |
| Native automatic policy | Actual SolidWorks preferences were AutoRecover **enabled**, native Backup **disabled**, interval **1 minute**, mode **2**. The harness read those settings without changing them. `auto` mode, with no interval override, started real worker **37156**, following the 60-second native interval. This was not the forced-mode fallback. |
| Recovery copy | A controlled unsaved dimension change from 2 mm to 3 mm produced a **39,935-byte** snapshot on the verified SanDisk. Snapshot and manifest hashes were checked; original document path, dirty state and disk bytes remained unchanged. Worker 37156 then stopped naturally with code 0. |
| Reopen acceptance | After completely unloading the unsaved document, the original disk file reopened at **0.0019999999999999983 m** and a SHA-matched workspace copy of the snapshot reopened at **0.003 m**. Both had zero external references/dependencies. No source save was performed. |
| Normal cleanup | All documents were unloaded before `ExitApp`. An already-held exact PID/start/image handle signaled exit code **0**; the watcher completed naturally after **4.417 seconds**, with no exception or breakpoint dump and classification `no_captured_exception`. No force termination or debugger detach was requested. |

The unchanged original file SHA256 is
`13c2884eee513e9eae50bd3a589ccb37fc5523d565175340887c3972ac69ed85`;
the snapshot and its workspace verification copy share
`736de8edaa32b3d57f081d6c4594ee2d123b7072895c7f220533590908857fb0`.

The actual embedded policy request also has
[four offline controls](../test-results/recovery-reservation-fence/verify_harness_policy_offline.json):
enabled native policy, disabled policy with explicit fallback labelled separately,
a native-fault marker and a watcher exit. Each fault control stopped subsequent
preference getters and worker startup. Native disabled preferences were **not**
forced on the real CAD instance merely to exercise a branch.

The [owned native harness](../tests/verify_owned_recovery_native.py) and
[synthetic legacy harness](../tests/verify_owned_recovery_legacy_native.py) are
manual, machine-specific, one-shot acceptance scripts. They are outside unittest
discovery and require fresh owned evidence paths; they do not launch CAD. Failed
fixture/setup attempts remain preserved separately from the successful receipts.

## Deployment boundary

Native acceptance covers this private standalone part and the changed worker
lifecycle. It does not add assembly/drawing acceptance or prove a cause for other
CAD exits. Live deployment and safe remediation of the actual MR12 legacy
reservation still require verification. No production MCP runtime, another
chat's configuration or actual reservation was modified during this isolated
implementation and acceptance run. Do not describe MR12's backups as restored
until its real monitor and backup outputs have been verified after deployment.
