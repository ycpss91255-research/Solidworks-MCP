# MR12 assembly state validation (2026-10-12)

This records a successful private model-state restoration, not completion of
the automatic backup goal. The original full-generation manifest remains failed.

## Findings

Fresh independent applications opened the source fixture and the repaired
copy. Both enumerated 1,405 private Pack and Go sources and 2,853 assembly
occurrences in configuration `MR12`. The source volume was
34.574441721795324 m³; the copied model initially had 34.574494772790054 m³.

Comparing occurrence model paths and transforms numerically showed every model
and placement matched. JSON string comparisons initially overcounted differences
because `-0.0` and `+0.0` serialize differently. Numeric tuple comparisons
removed that artifact. Exactly 26 occurrences nevertheless differed in
suppression: the source had 67 suppressed occurrences, and the copy had 41.
The differing leaves were below electrical subassemblies. Pack and Go's
`IncludeSuppressed` was already true; that option alone does not explain or
resolve the changed states.

## Private restoration

`component_states.py` matches every occurrence by canonical source model and
16-value placement transform before making changes. It rejects missing/moved
occurrences and coincident occurrences with conflicting desired suppression.
It verifies each applied change and the complete final occurrence state.
The caller remains responsible for PID ownership, private file checks and saving.

Only private copied models were editable in PID 13556. Restoring the desired
suppression required 14 native setter calls because some subassembly changes
also updated other occurrences. All 2,853 occurrence states then matched;
the volume became exactly the source value. Dirty documents and the root were
saved only after their paths were checked inside the private generation.

After normal application exit, fresh PID 36036 reopened the saved private root
read-only. All 2,853 normalized model paths, placements and suppression states
matched the source, with 67 suppressed occurrences. The volume was
34.574441721818275 m³, within 1e-9 m³ of the source. Pack and Go enumerated
1,405 sources, all inside the private generation. No memory dialog was dismissed;
the open operations explicitly chose cancellation for such a warning.

The fresh reopen returned error code 2 and warning code 0 despite returning a
model. Its cause has not been established. The source occurrence metadata does
contain suppressed references to old external locations; do not infer from
this alone that they account for that error, or claim an error-free restore.

## Changes and remaining work

Real native assembly snapshots now capture active configuration, occurrence
model paths, transforms, suppression, instance names and referenced
configurations in their manifests. They read that state again after packaging;
an occurrence-state change cannot be hidden by an unchanged document dirty flag.

The suppression restoration utility is not yet an automatic repair pipeline.
An independent repair design must address the STEP loaded-source cache,
manifest every additional STEP file, restore assembly states in private copies,
verify them after reopening, and finalize only after source preservation checks.
Existing source CAD must never be closed as a backup repair step. Further
named configurations, mates and other advanced states remain outside this test.

Ignored evidence under `test-results/mr12-isolated-proof`:

- `full-repaired-restore.json` and `fresh-source-comparison.json`
- `full-pose-comparison.json` and `suppression-pack-policy.json`
- `suppression-restoration-before-save.json`
- `suppression-restoration-saved.json`
- `suppression-restoration-reopened.json`

All owned test applications exited normally; working PIDs 2836 and 19780 were
not targeted. The full non-CAD suite passes 180 tests. Only the fork's
`codex/pid-isolation` branch receives source changes; `main` is unchanged.
