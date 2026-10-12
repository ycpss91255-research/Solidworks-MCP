"""Match assembly occurrences by model and placement before restoring suppression."""
from collections import Counter,defaultdict
import math

def capture_assembly_state(doc,major):
    """Read effective occurrence state from the already bound assembly."""
    from pathlib import Path
    from win32com.client import gencache
    from .recovery_snapshot import get0
    module=gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}',0,major,0)
    assembly=module.IAssemblyDoc(doc._oleobj_)
    rows=[]
    for raw in assembly.GetComponents(False) or ():
        component=module.IComponent2(raw._oleobj_)
        path=get0(component,'GetPathName')
        transform=get0(component,'Transform2')
        row={'source_path':str(Path(path).resolve()).casefold() if path else '',
             'matrix':list(get0(transform,'ArrayData')) if transform is not None else None,
             'suppressed':bool(component.IsSuppressed()),
             'reference_configuration':get0(component,'ReferencedConfiguration'),
             'name':get0(component,'Name2')}
        occurrence_key(row);rows.append(row)
    configuration=get0(get0(doc.ConfigurationManager,'ActiveConfiguration'),'Name')
    return {'configuration':configuration,'occurrences':rows}

def occurrence_key(row):
    if type(row.get('suppressed')) is not bool:
        raise ValueError('Suppression must be an explicit boolean')
    path=row['source_path']
    if not isinstance(path,str):raise ValueError('Occurrence model path must be a string')
    matrix=row['matrix']
    if matrix is not None:
        if len(matrix)!=16 or any(not math.isfinite(float(v)) for v in matrix):
            raise ValueError('Occurrence transform must contain 16 finite values')
        # Numeric tuples equate -0.0 and +0.0; JSON string keys do not.
        matrix=tuple(round(float(v),10) for v in matrix)
    return path.casefold(),matrix

def restore_suppression(components,desired,read,write,verify=lambda:None):
    """The caller must bind, own and save the private model; never moves components.

    Refuse before mutation unless every occurrence has the same model and
    placement, and coincident occurrences agree on the desired suppression.
    """
    verify();components=list(components);desired=list(desired)
    expected=defaultdict(set)
    for row in desired:expected[occurrence_key(row)].add(row['suppressed'])
    if any(len(values)!=1 for values in expected.values()):
        raise ValueError('Coincident occurrences have ambiguous suppression states')
    current=[read(component) for component in components]
    if Counter(map(occurrence_key,current))!=Counter(map(occurrence_key,desired)):
        raise ValueError('Private assembly occurrences do not match the source models and placements')
    changed=0
    for component,row in zip(components,current):
        verify();target=next(iter(expected[occurrence_key(row)]))
        # One shared subassembly update may already change another occurrence.
        if read(component)['suppressed']==target:continue
        write(component,target)
        if read(component)['suppressed']!=target:
            raise RuntimeError('Component suppression change was not applied')
        changed+=1
    verify();after=[read(component) for component in components]
    def full_key(row):return occurrence_key(row),row['suppressed']
    if Counter(map(full_key,after))!=Counter(map(full_key,desired)):
        raise RuntimeError('Restored component states do not match the source')
    return {'changed_occurrences':changed,'verified_occurrences':len(after)}
