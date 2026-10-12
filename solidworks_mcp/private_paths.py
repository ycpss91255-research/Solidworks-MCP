"""Canonicalize native output paths without repeating missing-parent walks."""
from pathlib import Path


def canonical_outputs(paths):
    parents={}
    result=[]
    for name in paths:
        path=Path(name)
        # Follow existing file symlinks as well as parent aliases/junctions.
        if path.name in ('','.','..') or path.is_symlink():
            result.append(path.resolve())
            continue
        parent=path.parent
        if parent not in parents:parents[parent]=parent.resolve()
        result.append(parents[parent]/path.name)
    return result
