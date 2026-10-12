# Explicit part recovery snapshots

`create_recovery_snapshot` creates a native private part copy through an
already-connected, PID-bound MCP. This is the first implemented recovery-copy
operation; it does not restore SolidWorks native AutoRecover or provide a
timer. Assemblies and drawings are deliberately unsupported until their
references can be recovered and verified without saving original components.
External reference files belonging to a part are not packaged by this tool.
The overall journal / recovery goal remains incomplete.

After connecting to this checkout's configured PID:

```json
{"directory":"C:/work/session-a/.codex/recovery"}
```

Pass this object to `create_recovery_snapshot`. The directory must be absolute
and belong to this session. Each process creation identity has its own folder,
and each invocation creates a unique generation containing `part.SLDPRT` and
`manifest.json`. Existing snapshots are retained; nothing is automatically
overwritten or deleted. Restoration is a separate explicit open operation.

The operation checks the configured application PID and holds a process handle.
It fingerprints the saved original file, records its path, title and unsaved
flag, and invokes only SaveAs3 with Silent|Copy (options 3). It checks the source
state and fingerprint afterward and records a complete manifest only when the
save API succeeds, a nonempty copy exists, and the source / PID checks pass.
A failed operation retains a failed manifest and any partial output for
diagnosis; it does not report a recovery copy as successfully completed.

It never calls SaveReferenced, saves the source, reconnects, launches a new CAD
process, takes over another PID, or dismisses dialogs. Connect failure must be
handled according to the workspace's PID isolation rules. No periodic policy
or snapshot root is enabled globally or in another session by this change.
An unsaved new part has no original disk fingerprint. A loaded part whose
original file is missing may also be copied; the tool verifies that it does
not recreate that original path as a side effect.

## Evidence and remaining validation

The underlying copy operation was live-tested on a private SW2023 test PID:
a 5 mm cylinder baseline was changed to 6 mm without saving. SaveAs3 options 3
created a private copy while preserving original path, dirty flag and volume.
The source was closed without saving; reopening the copy through the same
PID-bound MCP recovered one body with volume 1.884955592153876e-6 cubic metres.
The two working SolidWorks instances were left running throughout.

The new tool's guards and MCP schema/dispatch are tested without CAD. That
earlier live test used execute_python; the new endpoint still needs its own
live invocation and restoration test. Additional required work includes a
session-owned scheduling / crash-lifetime policy, assembly/reference recovery,
unsaved-new-document and drawing coverage, and actual native AutoRecover
validation. Do not present this manual part tool as complete automatic recovery.

The prior live test encountered a real low-memory warning on a later reopen;
its explicitly selected cancel action successfully closed that warning. Before
further live tests, inspect current resources and the test PID's actual state.
Do not reopen an already-loaded document or close a working chat's SolidWorks
to make room for a test.

Run the non-CAD checks:

```powershell
python -m unittest tests.test_recovery_snapshot -v
python -m unittest discover -s tests -p 'test_*.py' -q
```

Official API references:
- https://help.solidworks.com/2017/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDoc2~SaveAs3.html
- https://help.solidworks.com/2025/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swSaveAsOptions_e.html
