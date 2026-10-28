# Rebasing references after a move or a new worktree

SOLIDWORKS stores the full path of every referenced file inside the referencing file (assembly -> parts,
drawing -> assembly). After a repository is moved to another folder or drive, or checked out as another git
worktree, those stored paths still point at the old location.

## What goes wrong without a rewrite

Measured on SOLIDWORKS 2023: a 21-file tree (3 assemblies, 4 parts, 7 drawings) was copied to another drive and
the copied drawing was opened read-only without touching its references.

| | Documents loaded from the copy | Documents loaded from the OLD location |
|---|---|---|
| Opened as is | 1 (the drawing itself) | **7** |
| After `rebase_references.py --apply` | **8** | 0 |

SOLIDWORKS silently loaded the parts and assemblies that still existed at the stored paths. In a multi-worktree setup
that means editing, or saving over, a file in a different worktree than the one you think you are in.

## Tool

`rebase_references.py` rewrites the references of **closed** files under `--new-root` from `--old-root` to `--new-root`.
It lists references with `ISldWorks.GetDocumentDependencies2` and changes them with `ISldWorks.ReplaceReferencedDocument`,
both of which work without opening a document. Logic and tests live in `solidworks_mcp/reference_rebase.py` and
`tests/test_reference_rebase.py`.

```
# 1. preview (default): reads references only, changes nothing
python rebase_references.py --old-root C:/repo/wt-a --new-root D:/moved/wt-b --pid 12345

# 2. apply, using one chat-owned instance started and retired by the tool
python rebase_references.py --old-root C:/repo/wt-a --new-root D:/moved/wt-b --launch --session-file C:/me/own-session.json --apply --report report.json
```

`--pid` attaches to an existing PID-bound instance and never launches another. `--launch` needs a NEW absolute
`--session-file`, waits for the resource gate, starts one instance through the guarded launcher and retires only that
instance through a held handle. Exit code: 0 on success or preview, 1 when an applied run did not verify, 2 when refused.

Run it on the **copy** (the new location). The old location is only used to recognise which references to rewrite.

## Safety rules (all covered by tests)

- Only files under `--new-root` are changed; the old root is never a target.
- A reference is rewritten only when the file it would point to exists under the new root; otherwise it is reported as
  `missing_target` and left alone.
- References outside both roots (shared libraries) and non-native references (STEP, ...) are left alone and listed.
- Files with a `~$` lock sibling are skipped and listed; the run refuses before changing anything if a target file is open in
  the instance.
- Roots must be absolute, different, and not nested.
- After an applied run every reference is read again; `verified` is true only when nothing failed and nothing still points
  at the old root. A second run changes nothing.

## Verification (SOLIDWORKS 2023, 2026-10-28)

Copy of the 21-file tree on another drive, references still pointing at the original tree:

1. preview: 24 references would be replaced, nothing changed
2. apply: 24 replaced, 0 failed, 0 still pointing at the old root, verified
3. preview again: 0 to replace, 24 already in the new root
4. independent check in a fresh instance: 8 documents loaded, all under the new root, none under the old root
5. the old tree: size, modification time and SHA256 of all 21 files unchanged

## Limits

- Tested on one tree and one SOLIDWORKS version (2023). Not tested: very large trees, PDM-managed files, drawings with sheet
  formats or templates stored outside the roots, references that are not document references.
- The lock check looks for `~$<name>` next to the file; it cannot see a file held open without a lock file.
- Relative references: no official statement was found, and none of this relies on them.
- The Referenced Documents search-folder option of SOLIDWORKS is a separate, global per-user mechanism and was not
  tested here.
- References in files that were already opened and saved in the new location by SOLIDWORKS may already be correct; the
  tool reports them as `ok`.
