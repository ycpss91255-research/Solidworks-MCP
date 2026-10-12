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
helper. A nonzero or unverified reopen error prevents source finalization.
The source owner still verifies its original document, occurrence state,
loaded-source states, disk hashes and PID/creation identity before completion.
The optional processor is not yet connected to automatic worker lifecycle;
no working session was given a helper or retargeted in this change.

## Real integration on 2026-10-12

Dedicated owned PID 28108 processed the detached MR12 test package with the
captured source state. The combined operation verified 2,853 occurrences,
recorded three STEP aliases and their hashes, saved/reopened the private root,
and exited normally with no documents remaining. Its reopen returned error 2.
The source fixture also contains seven distinct missing suppressed references
and no missing active reference paths. This inventory alone does not prove
the load error's cause. The source-finalization gate therefore still rejects
this result, and the original failed manifest was not promoted.

An initial test attempted `ShowConfiguration2` even when the desired
configuration was already active; its false return was incorrectly interpreted
as a missing configuration. The implementation now checks the actual active
configuration first and verifies it after switching. The corrected real
combined integration passed its occurrence check.

Evidence is ignored under `test-results/mr12-isolated-proof`:
`integrated-private-repair.json` and `source-missing-reference-inventory.json`.
The non-CAD suite passes 192 tests. Working PIDs 2836 and 19780 were not targeted;
only the fork's `codex/pid-isolation` branch is updated. Automatic worker
integration, load-error resolution, and end-to-end source/helper validation
remain required before the full backup objective is complete.
