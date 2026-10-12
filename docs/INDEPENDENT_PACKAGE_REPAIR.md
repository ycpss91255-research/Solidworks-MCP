# Independent private package repair

`package_repair.py` combines the tested STEP and occurrence-state repair paths.
It never finalizes the source application's backup manifest.

The caller supplies an explicitly bound helper application, its PID and an
absolute managed session file. The session must identify that PID/creation
time and have role `recovery_repair`. The helper must be empty and distinct
from the source PID. The function does not launch CAD or attach a generic COM
application; it refuses an existing document rather than closing it.

Before mutation, every package output must be absolute, unique, nonempty and
inside the generation, and cannot equal any source path. STEP primaries must
match their source hashes. Original STEP basenames are copied beside native
owners using exclusive file creation; existing aliases must be byte-identical.
All extra copies and hashes are included in the repair result.

The helper repairs recorded STEP links, opens only the private assembly,
selects the captured source configuration when necessary, restores suppression
only after complete model/placement matching, and saves only private documents.
It closes those documents and reopens the saved root read-only to verify all
occurrences. This reopening is in the same helper process; the result records
`fresh_process_reopen=False` and does not claim a fresh-process verification.

`snapshot_package` now accepts an independent `package_processor` callback.
Its result must cover all primary outputs and declared STEP aliases, have
unchanged matching hashes, verify every occurrence and identify a separate
helper. Unverified load errors prevent source finalization. The sole supported
nonzero exception is FileNotFound (2) with an exactly preserved, nonempty
source inventory of missing suppressed references, zero missing active
occurrences and no new missing path. Such completion retains the source
limitation in its manifest; it cannot recover files missing before backup.
The source owner still verifies its original document, occurrence state,
loaded-source states, disk hashes and PID/creation identity before completion.
Automatic batches now select the processor when
`SOLIDWORKS_RECOVERY_REPAIR_SESSION_FILE` explicitly names a separate owned
helper. The helper state must have role `recovery_repair`, its own live PID and
creation time, and `source_session_file` equal to the source's absolute state
path. Neither the service nor worker launches CAD. Missing/unowned helpers
return an explicit error. No working session was given a helper or retargeted.

The private worker request/result have matching random tokens. Helper startup
and recursive monitoring are disabled. Source PID/creation time and both
session ownership records are rechecked during repair; one mutex serializes
requests to a helper. The worker connects through the existing PID-bound
automation backend and never falls back to a generic COM application.

## Real integration on 2026-10-12

Dedicated owned PID 28108 processed the detached MR12 test package with the
captured source state. The combined operation verified 2,853 occurrences,
recorded three STEP aliases and their hashes, saved/reopened the private root,
and exited normally with no documents remaining. Its reopen returned error 2.
The source fixture also contains seven distinct missing suppressed references
and no missing active reference paths. This inventory alone does not prove
the load error's cause, and the original failed manifest was not promoted.

On 2026-10-13, a fresh owned PID 33000 opened the source fixture itself and
returned error 2, warning 0. Numeric missing-reference inventories were then
compared against the independently reopened repaired model: all seven missing
paths and suppressed occurrence counts were unchanged, with no missing active
occurrence. Revalidation accepted the repair proof and all 1,408 declared file
hashes (1,405 primaries plus three STEP aliases), retaining the original failed
generation status. The acceptance exception is now restricted to exactly this
preserved source limitation. Active missing files, new missing paths, other
error flags and unverified inventories still prevent completion.

An initial test attempted `ShowConfiguration2` even when the desired
configuration was already active; its false return was incorrectly interpreted
as a missing configuration. The implementation now checks the actual active
configuration first and verifies it after switching. The corrected real
combined integration passed its occurrence check.

Evidence is ignored under `test-results/mr12-isolated-proof`:
`integrated-private-repair.json`, `source-missing-reference-inventory.json`,
`source-open-error-baseline.json` and `source-limitation-acceptance-proof.json`.
The non-CAD suite passes 201 tests. Working PIDs 2836 and 19780 were not targeted;
only the fork's `codex/pid-isolation` branch is updated. Automatic worker
configuration, end-to-end source/helper validation and final completion audit
remain required before the full backup objective is complete.
