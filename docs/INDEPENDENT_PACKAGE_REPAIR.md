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

## Copy-only staging investigation on 2026-10-13

The full source/helper test caught a disk change to the private fixture's root
assembly during source-side `SavePackAndGo`. RAM document state and all 2,853
occurrences were unchanged, but that is insufficient source preservation.
The generation remains failed. Neither working PID 2836 nor 19780 was targeted.

A separate `SaveAs3(path, 0, 3)` (Silent | Copy, without SaveReferenced) root-copy
test preserved both the source hash and RAM document state. Native Pack and Go
now supplies metadata only; it never saves source packages. Staging captures
the root and dirty loaded documents with copy-only saves and copies clean saved
dependencies as bytes. Native packaging requires an explicitly owned helper;
it fails safely without one. The helper rewrites references in closed private
native files before opening an assembly. STEP import repair and occurrence
restoration then operate on those copies.

The complete live source/helper run passed on 2026-10-13. Source PID 34296
retained its dirty root, all loaded-document states, all source hashes and its
2,853 occurrence states. Helper PID 39984 rewrote the closed private references,
repaired STEP links, saved/reopened the private root and verified all 2,853
occurrences. The complete generation has 1,408 hashed files including three
STEP aliases. Its source's existing suppressed missing-reference limitation
remains recorded; reopening uses that exact validated exception. This is an
end-to-end manual package test, not a completed automatic-worker deployment or
a new-process restore test. The non-CAD suite passes 205 tests.

Evidence: `test-results/mr12-isolated-proof/source-helper-complete.json` and
`C:/SWP/ab1d/pfa7dbe386a/amxtzl7he/manifest.json` (private ignored artifacts).
Drawing packages currently fail safely with this assembly-only helper; their
earlier Pack and Go tests are historical and do not validate copy-only staging.

The earlier stdio-child repair process stalled before Python initialization.
The desktop-parent worker path completed the isolated repair instead; request
tokens and the helper ownership/identity checks still apply. A response timeout
does not cause this service to launch a replacement worker.

## Fresh restore and rack validation

A fresh owned PID 39612 reopened the complete MR12 package and verified all
2,853 occurrences including referenced configurations, 1,405 private primary
sources and volume 34.57444172181828 m³. All 1,408 file hashes remained unchanged.
It returned the same validated missing-suppressed-reference error 2, warning 0,
and then exited normally. Evidence: `copy-staging-fresh-restore-proof.json`.

The rack fixture uses copied files from `後推式貨架_原生聯動_v4.SLDASM`; no
formal model was opened in the test CAD. Closed-file private reference rewrites
prepared its inputs, and all original file hashes stayed unchanged. A renamed
fixture/package produced invalid mirrored wheel occurrences. Keeping original
basenames in distinct private subfolders fixed the actual test: seven files and
all 108 occurrences were verified, source disk/RAM state was preserved and the
private root reopened with error 0. The native metadata no longer adds prefixes.

One beam already references the absent `D:/push_back/1重型货架.SLDASM` context.
Such existing absent native context links are captured by source owner, retained
exactly and verified from closed final copies. They remain explicit source
limitations; they are not recovered files. New missing paths, existing external
files and changed missing-context inventories still reject completion. Recorded
and resolved aliases may be paired only when native reference counts, order and
labels agree and the resolved path is in the enumerated source set.

Evidence: ignored `test-results/rack-private-proof/manual-backup.json`,
`fixture-input.json` and `state-differences.json`. The current non-CAD suite
passes 210 tests. The real default-mode reconnect test also passed: native
preferences were AutoRecover enabled, backup disabled, one-minute mode; both
MCP connections used that 60-second policy without a preference write. The
first MCP exited, worker PID 43684 produced a complete batch, and the second
MCP reused the same worker and creation identity. Two complete seven-file
packages were independently validated, 84.860372 seconds apart (one native
interval after the prior package work); formal source hashes stayed unchanged.
The private stop marker then stopped that identified worker normally.
Evidence: `rack-private-proof/native-timed-reconnect-proof.json` and the two
`native-*-connect.json` files. A fresh-process rack restore, regression validation
of the MR12 path with preserved basenames and final deployment audit remain.

The fresh rack restore then passed in owned PID 27296: all 108 occurrences,
referenced configurations, seven private sources and volume
0.06739667792959786 m³ matched the timed snapshot, with error/warning 0 and
unchanged backup hashes. It exited normally. Evidence:
`rack-private-proof/fresh-restore-proof.json`.

MR12 regression with preserved basenames also completed: source PID 35832,
helper PID 40620, all 2,853 occurrences and source disk/RAM state preserved.
The complete package has 1,405 primaries and two additional STEP aliases (one
alias is already a primary), totaling 1,407 hashes. Evidence:
`mr12-isolated-proof/preserved-names-complete.json`.

Read-only deployment inspection found the existing MR12 worker PID 24684 still
live with its old status `snapshot_in_progress`, last updated around 00:14,
and no `follow_native_preferences` flag. It was not stopped or retargeted, and
its status does not prove present protection. The two working CAD PIDs were
not controlled. Updating production sessions remains a separate incomplete
deployment step; this document does not claim their workers were migrated.

Current local work groups output files by a compact canonical-parent hash,
retaining basenames and STEP adjacency instead of reproducing the deep source
hierarchy. This keeps room in the default `%LOCALAPPDATA%/SWMCP/<session-hash>`
root. The real default-directory MR12 run passed: 1,405 primaries, 1,407 hashes,
2,853 verified occurrences and preserved source disk/RAM state. Windows resolved
the requested LocalAppData folder to the Codex package's LocalCache directory;
the final manifest and all mappings retain that authoritative canonical root.
Evidence: `mr12-isolated-proof/compact-default-complete.json`. The non-CAD suite
passes 211 tests. A fresh owned PID 32184 then reopened this compact generation:
2,853 occurrences and referenced configurations matched, all 1,405 primary
sources were private, volume was 34.57444172181828 m³ and all 1,407 hashes
remained unchanged. The existing source's missing-reference flag 2 was retained,
with warning 0 and no memory-warning event. It exited normally. Evidence:
`mr12-isolated-proof/compact-default-fresh-restore-proof.json`. Production
session migration remains pending authorization; see `BACKUP_COMPLETION_AUDIT.md`.

Nonblocking `py-spy` stack inspection of the old MR12 worker pinpointed its
wait in `NativePack.__init__` at `extension.GetPackAndGo()` (old line 34), before
package saves. This is evidence of its current wait, not a diagnosis of the
underlying SolidWorks cause. It was neither paused nor terminated. The ordinary
document-dependency API was tested as a possible replacement on this chat's
fixture; it omitted six saved inactive dependencies and three STEP sources,
so it cannot replace Pack and Go enumeration without additional verified
coverage. A separate extension-dependency probe returned a server exception;
it was not used as a fallback. See `BACKUP_WORKER_MIGRATION.md` for the pending,
cross-chat-authorized deployment plan.
