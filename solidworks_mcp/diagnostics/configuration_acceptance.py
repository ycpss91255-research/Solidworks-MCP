"""Read-only geometry evidence for an already connected private CAD fixture."""
import math
import os
from pathlib import Path


def _feature_faces(types, part, name):
    raw = part.FeatureByName(name)
    assert raw, f'missing hole feature: {name}'
    return types.IFeature(raw._oleobj_).GetFaces() or []


def assert_geometry(observation, expected, tolerance_mm=.001):
    """Reject cached dimensions as a substitute for rebuilt, physical geometry."""
    assert observation.get('configuration') == expected['configuration'], 'configuration mismatch'
    assert observation.get('rebuild') is True, 'rebuild failed or unverified'
    assert observation.get('feature_errors') == [], 'feature errors or missing feature evidence'
    assert observation.get('equation_errors') == [], 'equation errors or missing equation evidence'
    assert observation.get('equation_count') == expected['equation_count'], 'equation count mismatch'
    count = observation.get('solid_body_count')
    assert type(count) is int and count > 0, 'no verified solid body'
    for name in ('length_mm', 'hole_span_mm'):
        value = observation.get(name)
        assert type(value) in (int, float) and math.isfinite(value), f'{name} missing/nonfinite'
        assert abs(value - expected[name]) <= tolerance_mm, f'{name} mismatch: {value}'


def observe_configuration(sw, doc_path, fixture_dir, expected_pid, rebuild_result):
    """Collect through existing PID-bound COM only; never open/rebuild/save/close.

    The caller supplies the actual result of its preceding ForceRebuild3. On a
    failed rebuild, physical-hole traversal is omitted and acceptance stays red.
    All loaded document paths must belong to the supplied private fixture.
    """
    from win32com.client import gencache
    assert type(expected_pid) is int and expected_pid > 0, 'explicit positive PID required'
    configured = os.environ.get('SOLIDWORKS_TARGET_PID')
    assert not configured or int(configured) == expected_pid, 'configured PID mismatch'
    pid = sw.GetProcessID
    assert (pid() if callable(pid) else pid) == expected_pid, 'connected PID mismatch'
    fixture = Path(fixture_dir)
    path = Path(doc_path)
    assert fixture.is_absolute() and path.is_absolute(), 'private absolute paths required'
    fixture, path = fixture.resolve(), path.resolve()
    assert path.is_relative_to(fixture), 'document escapes private fixture'
    revision = sw.RevisionNumber
    revision = revision() if callable(revision) else revision
    types = gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}', 0,
                                 int(revision.split('.')[0]), 0)
    app = types.ISldWorks(sw._oleobj_)
    loaded_paths = [types.IModelDoc2(raw._oleobj_).GetPathName() for raw in app.GetDocuments() or []]
    assert all(p and Path(p).resolve().is_relative_to(fixture) for p in loaded_paths), 'non-private loaded document'
    raw = app.GetOpenDocumentByName(str(path))
    assert raw, 'fixture document must already be open'
    doc = types.IModelDoc2(raw._oleobj_)
    assert doc.GetType() == 1 and Path(doc.GetPathName()) == path, 'requested part mismatch'
    errors = []
    raw = doc.FirstFeature()
    while raw:
        feature = types.IFeature(raw._oleobj_)
        error = feature.GetErrorCode2(True)
        if error[0]:errors.append({'feature':feature.Name, 'code':error[0]})
        raw = feature.GetNextFeature()
    eq = types.IEquationMgr(doc.GetEquationMgr()._oleobj_)
    equation_errors = []
    for index in range(eq.GetCount()):
        value = eq.Value(index)
        if eq.Status == -1 or not math.isfinite(value):
            equation_errors.append({'index':index, 'status':eq.Status, 'value':value})
    part = types.IPartDoc(doc._oleobj_)
    bodies = part.GetBodies2(0, False) or []
    centers = set()
    if rebuild_result is True and not errors:
        radius = types.IDimension(doc.Parameter('D1@孔草圖')._oleobj_).SystemValue / 2
        for name in ('端孔', '端孔鏡射'):
            for raw in _feature_faces(types, part, name):
                face = types.IFace2(raw._oleobj_)
                surface = types.ISurface(face.GetSurface()._oleobj_)
                if surface.IsCylinder():
                    params = list(surface.CylinderParams)
                    if abs(params[6] - radius) < 1e-8 and abs(abs(params[5])-1) < 1e-6:
                        # This fixture's hole axes are parallel to local Z.
                        # Cylinder origins may differ along that axis; compare
                        # projected axis positions, not arbitrary origin depth.
                        centers.add((round(params[0],9),round(params[1],9),0.0))
    span = max((math.dist(a,b)*1000 for a in centers for b in centers), default=None)
    return dict(configuration=doc.ConfigurationManager.ActiveConfiguration.Name,
        rebuild=rebuild_result, feature_errors=errors, equation_errors=equation_errors,
        equation_count=eq.GetCount(), solid_body_count=len(bodies),
        length_mm=types.IDimension(doc.Parameter('D1@撐桿本體')._oleobj_).SystemValue*1000,
        hole_span_mm=span, hole_centers_m=sorted(centers))
