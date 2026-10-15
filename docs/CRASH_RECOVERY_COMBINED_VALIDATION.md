# Combined crash and recovery validation

The isolated `codex/crash-recovery-validation` branch combines CloseDoc diagnostics
`11d63b2fd0f509fb1e08961394a98dc8cd5d13bc` with recovery fencing
`b64a82b2dad927fd2a98a820dadb37f46261ad14`, cherry-picked as HEAD
`797b48f88298579190c4edc4830dab87bec360d2` from base `5266061`.
The only later code change is the test-only adjustment in
[tests/test_recovery_startup_windows.py](../tests/test_recovery_startup_windows.py).

| Validation | Actual result |
| --- | --- |
| First complete combined run | 370 passed, 1 ERROR out of 371; 31.034 s. Original mixed result remains preserved. |
| One unchanged targeted rerun | 1 passed; 2.030 s. No repeated reruns were used to replace the first result. |
| Test-only deterministic RED | 1 failure, 1 pass: unstable inventory made 2 snapshots rather than the expected maximum of 6. |
| Test-only targeted GREEN | 3 passed; 2.461 s, including real Windows preclaim recovery. |
| Final combined run | 373/373 passed; 23.627 s. |
| Source and review checks | 123 source/test/document hashes unchanged during the final run; production hashes unchanged from the mixed run; diff check and the 22 existing document links passed. Independent test-only review found no blocker. |

The first failure occurred at the real scanner's double-snapshot comparison:
Python process inventory changed, so `RecoveryInventoryUncertain` refused
retirement. The test had assumed machine-wide inventory would remain stable.
The changed process was not recorded. The temporary failed fixture had already
been removed by unittest cleanup; exact byte preservation is verified by the new
tests, not retrospectively claimed for that first run.

The test now permits at most three attempts, catching only
`RecoveryInventoryUncertain`. Before another attempt it checks unchanged pending
bytes, no archive/status, unchanged child list, and zero worker/process spawn.
The third refusal remains a failure. Alternating fake process snapshots exercise
the real scanner's refusal on all three attempts; an unrelated error must escape
on the first attempt. Production scanner, locks, retirement and worker behavior
are unchanged. The final test SHA256 is
`b31d1c800a45ff6a52ae99d265d9eb893c7179303d2c1c1873a3cfc9c15a2224`.

These tests made no CAD calls or UI operations and did not alter live/FIX source,
real session metadata or reservations. The combined branch is not deployed.
This validates software integration and diagnostic behavior; it does not claim
to repair SolidWorks native crashes. Deployment is tracked separately from branch commits.

The exact small evidence files below need explicit `git add -f` because
`test-results` is ignored. There are **15 files, 218,083 bytes total**
(212.97 KiB). The test and this document use ordinary `git add`.
The directory-specific attributes preserve captured evidence bytes and log
whitespace. No dump, model or large native artifact belongs in this list.

| Exact repository path to force-add | Bytes |
| --- | ---: |
| [test-results/crash-recovery-validation/.gitattributes](../test-results/crash-recovery-validation/.gitattributes) | 135 |
| [test-results/crash-recovery-validation/combined-green-v1.json](../test-results/crash-recovery-validation/combined-green-v1.json) | 32,367 |
| [test-results/crash-recovery-validation/combined-green-v1-console.txt](../test-results/crash-recovery-validation/combined-green-v1-console.txt) | 59,551 |
| [test-results/crash-recovery-validation/run_combined_validation_v1.py](../test-results/crash-recovery-validation/run_combined_validation_v1.py) | 3,894 |
| [test-results/crash-recovery-validation/targeted-preclaim-rerun-v1.json](../test-results/crash-recovery-validation/targeted-preclaim-rerun-v1.json) | 852 |
| [test-results/crash-recovery-validation/targeted-preclaim-rerun-v1-console.txt](../test-results/crash-recovery-validation/targeted-preclaim-rerun-v1-console.txt) | 330 |
| [test-results/crash-recovery-validation/bounded-retry-red.json](../test-results/crash-recovery-validation/bounded-retry-red.json) | 800 |
| [test-results/crash-recovery-validation/bounded-retry-red-console.txt](../test-results/crash-recovery-validation/bounded-retry-red-console.txt) | 1,187 |
| [test-results/crash-recovery-validation/bounded-retry-red-test.py](../test-results/crash-recovery-validation/bounded-retry-red-test.py) | 16,183 |
| [test-results/crash-recovery-validation/bounded-retry-green.json](../test-results/crash-recovery-validation/bounded-retry-green.json) | 805 |
| [test-results/crash-recovery-validation/bounded-retry-green-console.txt](../test-results/crash-recovery-validation/bounded-retry-green-console.txt) | 711 |
| [test-results/crash-recovery-validation/bounded-retry-test-only.patch](../test-results/crash-recovery-validation/bounded-retry-test-only.patch) | 5,881 |
| [test-results/crash-recovery-validation/combined-green-v2.json](../test-results/crash-recovery-validation/combined-green-v2.json) | 32,639 |
| [test-results/crash-recovery-validation/combined-green-v2-console.txt](../test-results/crash-recovery-validation/combined-green-v2-console.txt) | 58,399 |
| [test-results/crash-recovery-validation/run_combined_validation_v2.py](../test-results/crash-recovery-validation/run_combined_validation_v2.py) | 4,349 |
