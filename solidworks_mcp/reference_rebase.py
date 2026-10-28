"""Rewrite the references of CLOSED SOLIDWORKS files from an old root to a new root.

SOLIDWORKS stores the full path of every referenced file in the referencing file. After a repository is moved or
checked out in another worktree the stored paths still point at the old location, and SOLIDWORKS may even open the
files that still exist there. This module plans and applies a path rewrite on the copy in the new location:

* only files under the new root are ever modified; the old root is read-only knowledge, never a target;
* no document is opened: references are listed with ISldWorks.GetDocumentDependencies2 and changed with
  ISldWorks.ReplaceReferencedDocument, both of which work on closed files;
* a reference is only rewritten when the file it would point to exists under the new root;
* files with a ``~$`` lock sibling are skipped, and the run refuses if any target is open in the instance;
* the default is a dry run, and an applied run re-reads every reference to verify the result.
"""
import os
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PureWindowsPath
from typing import Callable, Iterable, List, Optional

NATIVE = {'.sldprt': 0, '.sldasm': 1, '.slddrw': 2}
STATUSES = ('replace', 'ok', 'missing_target', 'outside', 'non_native')


def norm(path) -> str:
    return str(PureWindowsPath(str(path))).casefold().rstrip('\\')


def under(path, root) -> bool:
    return norm(path).startswith(norm(root) + '\\')


def validate_roots(old_root, new_root) -> None:
    for root in (old_root, new_root):
        if not PureWindowsPath(str(root)).is_absolute():
            raise ValueError(f'Roots must be absolute paths: {root}')
    if norm(old_root) == norm(new_root):
        raise ValueError('The old and new roots are the same folder')
    if under(old_root, new_root) or under(new_root, old_root):
        raise ValueError('One root is inside the other; the rewrite would be ambiguous')


def order_files(files: Iterable[str]) -> List[str]:
    """Parts first, then assemblies, then drawings, so a referenced file is rewritten before its referrers."""
    return sorted(files, key=lambda f: (NATIVE.get(Path(f).suffix.lower(), 3), norm(f)))


@dataclass
class Action:
    file: str
    old: str
    new: Optional[str]
    status: str


def plan_file(file: str, refs: Iterable[str], old_root, new_root, exists: Callable[[str], bool] = os.path.isfile) -> List[Action]:
    actions, seen = [], set()
    for ref in refs:
        key = norm(ref)
        if key in seen:
            continue
        seen.add(key)
        if Path(ref).suffix.lower() not in NATIVE:
            actions.append(Action(file, ref, None, 'non_native'))
        elif under(ref, new_root):
            actions.append(Action(file, ref, None, 'ok'))
        elif under(ref, old_root):
            relative = PureWindowsPath(str(ref)).relative_to(PureWindowsPath(str(old_root)))
            target = str(PureWindowsPath(str(new_root)) / relative)
            actions.append(Action(file, ref, target, 'replace' if exists(target) else 'missing_target'))
        else:
            actions.append(Action(file, ref, None, 'outside'))
    return actions


def native_files(root) -> List[str]:
    return [str(p) for p in Path(root).rglob('*')
            if p.is_file() and p.suffix.lower() in NATIVE and not p.name.startswith('~$')]


def is_locked(file: str) -> bool:
    path = Path(file)
    return (path.parent / ('~$' + path.name)).exists()


def list_references(app, file: str) -> List[str]:
    flat = app.GetDocumentDependencies2(file, False, False, False) or ()
    if len(flat) % 2:
        raise RuntimeError(f'Unexpected dependency list for {file}')
    return list(flat[1::2])


def rebase(app, files: Iterable[str], old_root, new_root, apply: bool = False,
           exists: Callable[[str], bool] = os.path.isfile, locked: Callable[[str], bool] = is_locked) -> dict:
    validate_roots(old_root, new_root)
    ordered = order_files(files)
    for file in ordered:
        if not under(file, new_root):
            raise ValueError(f'{file} is outside the new root; only files under the new root may be modified')
    for file in ordered:
        if app.GetOpenDocumentByName(file) is not None:
            raise RuntimeError(f'{file} is open in SOLIDWORKS; close it first (references are rewritten on closed files)')
    skipped = [f for f in ordered if locked(f)]
    todo = [f for f in ordered if f not in skipped]
    actions: List[Action] = []
    for file in todo:
        actions += plan_file(file, list_references(app, file), old_root, new_root, exists)
    counts = Counter({status: 0 for status in STATUSES})
    counts.update(a.status for a in actions)
    report = {'mode': 'apply' if apply else 'dry-run', 'old_root': str(old_root), 'new_root': str(new_root),
              'files': len(ordered), 'locked_skipped': skipped, 'counts': dict(counts),
              'actions': [asdict(a) for a in actions], 'replaced': 0, 'failed': [], 'verified': None,
              'remaining_old': []}
    if not apply:
        return report
    for action in actions:
        if action.status != 'replace':
            continue
        if app.ReplaceReferencedDocument(action.file, action.old, action.new):
            report['replaced'] += 1
        else:
            report['failed'].append({'file': action.file, 'old': action.old, 'new': action.new})
    for file in todo:
        for ref in list_references(app, file):
            if under(ref, old_root):
                report['remaining_old'].append({'file': file, 'ref': ref})
    report['verified'] = not report['failed'] and not report['remaining_old']
    return report
