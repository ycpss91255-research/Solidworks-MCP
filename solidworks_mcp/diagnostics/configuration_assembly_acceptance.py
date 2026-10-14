"""Read-only assembly evidence and explicit occurrence/placement acceptance."""
import math
from pathlib import Path


def assert_brace_grid(hole_pairs, segment_count, total_height_m, width_m, tolerance=1e-6):
    """This fixture's physical diagonal endpoints: global Y height, global Z span."""
    assert type(segment_count) is int and segment_count>0
    assert len(hole_pairs)==segment_count, 'physical diagonal count mismatch'
    assert all(len(pair)==2 and all(len(p)==3 and all(math.isfinite(v) for v in p) for p in pair) for pair in hole_pairs), 'invalid physical endpoints'
    height=total_height_m/segment_count
    starts=[]
    for a,b in hole_pairs:
        assert abs(a[0]-b[0])<=tolerance, 'diagonal out of plane'
        assert abs(abs(a[1]-b[1])-height)<=tolerance, 'physical segment height mismatch'
        assert abs(abs(a[2]-b[2])-width_m)<=tolerance, 'physical span mismatch'
        starts.append(min(a[1],b[1]))
    starts.sort()
    assert all(abs(value-(starts[0]+index*height))<=tolerance for index,value in enumerate(starts)), 'physical pattern placement mismatch'


def transform_point(matrix, point):
    """SOLIDWORKS row-axis rotation, then scale and translation (meters)."""
    assert len(matrix)==16 and len(point)==3
    return [matrix[12]*sum(point[i]*matrix[3*i+j] for i in range(3))+matrix[9+j] for j in range(3)]


def assert_assembly(observed, baseline, expected_counts, tolerance=1e-8):
    """Compare a restored/roundtrip assembly to a previously verified baseline.

    This does not prove the baseline design correct. Changed-input positions need
    independent expected placements; never use the current result as its baseline.
    Counts concern unsuppressed occurrences grouped by referenced configuration.
    """
    def index(rows):
        result={}
        for row in rows:
            name=row['name']
            assert name not in result, 'duplicate occurrence name'
            matrix=row['matrix']
            assert len(matrix)==16 and all(type(x) in (int,float) and math.isfinite(x) for x in matrix), 'invalid placement matrix'
            assert type(row['suppressed']) is bool, 'missing suppression evidence'
            result[name]=row
        return result
    current, original=index(observed), index(baseline)
    assert current.keys()==original.keys(), 'occurrence inventory mismatch'
    for name,row in current.items():
        desired=original[name]
        for key in ('configuration','source_path','suppressed'):
            assert row[key]==desired[key], f'{name}: {key} mismatch'
        assert all(abs(a-b)<=tolerance for a,b in zip(row['matrix'],desired['matrix'])), f'{name}: placement mismatch'
    for configuration,count in expected_counts.items():
        assert type(count) is int and count>=0, 'invalid expected count'
        actual=sum(not row['suppressed'] and row['configuration']==configuration for row in observed)
        assert actual==count, f'{configuration}: actual occurrence count {actual}, expected {count}'


def observe_assembly(sw, types, assembly_path, fixture_dir, expected_pid):
    """Inspect an already open owned private assembly; no open/rebuild/save/close."""
    assert type(expected_pid) is int and expected_pid>0 and sw.GetProcessID()==expected_pid, 'PID mismatch'
    private=Path(fixture_dir)
    assert private.is_absolute(), 'absolute private fixture required'
    private=private.resolve()
    loaded=[types.IModelDoc2(raw._oleobj_).GetPathName() for raw in sw.GetDocuments() or []]
    assert loaded and all(p and Path(p).resolve().is_relative_to(private) for p in loaded), 'non-private document'
    path=Path(assembly_path).resolve()
    assert path.is_relative_to(private), 'non-private assembly'
    raw=sw.GetOpenDocumentByName(str(path))
    assert raw, 'open assembly required'
    doc=types.IModelDoc2(raw._oleobj_)
    assert doc.GetType()==2 and Path(doc.GetPathName()).resolve()==path
    assembly=types.IAssemblyDoc(doc._oleobj_)
    rows=[]
    for raw in assembly.GetComponents(False) or []:
        component=types.IComponent2(raw._oleobj_)
        source=component.GetPathName()
        assert source and Path(source).resolve().is_relative_to(private), 'non-private component reference'
        transform=component.Transform2
        assert transform, 'missing placement transform'
        rows.append(dict(name=component.Name2, source_path=str(Path(source).resolve()),
            configuration=component.ReferencedConfiguration,
            suppressed=bool(component.IsSuppressed()),
            matrix=list(types.IMathTransform(transform._oleobj_).ArrayData)))
    return sorted(rows,key=lambda row:row['name'])
