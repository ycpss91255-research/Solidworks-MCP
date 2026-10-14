"""Unvalidated rack repair candidate, invoked only through an owned PID-bound MCP.

No connection, launch, activation of the new configuration, rebuild, save, close
or recovery fallback is performed here. Geometry acceptance remains separate.
"""
from pathlib import Path


def apply_candidate(sw, interfaces, fixture_dir, expected_pid, diagonal_properties):
    assert type(expected_pid) is int and expected_pid > 0
    assert sw.GetProcessID() == expected_pid, 'PID mismatch'
    fixture = Path(fixture_dir)
    assert fixture.is_absolute()
    fixture = fixture.resolve()
    loaded = [interfaces.IModelDoc2(raw._oleobj_).GetPathName() for raw in sw.GetDocuments() or []]
    assert all(p and Path(p).resolve().is_relative_to(fixture) for p in loaded), 'non-private document'
    path = fixture/'支撐條.SLDPRT'
    raw = sw.GetOpenDocumentByName(str(path))
    assert raw, 'open private part required'
    doc = interfaces.IModelDoc2(raw._oleobj_)
    assert Path(doc.GetPathName()).resolve() == path
    assert sw.ActivateDoc3(doc.GetTitle(),False,0,0)[0]
    assert doc.ConfigurationManager.ActiveConfiguration.Name == '橫撐'
    eq = interfaces.IEquationMgr(doc.GetEquationMgr()._oleobj_)
    original = [eq.Equation(i) for i in range(eq.GetCount())]
    assert any(text.split('=',1)[0].strip() == '"D1@撐桿本體"' for text in original)
    if doc.GetConfigurationByName('斜撐'):
        assert doc.DeleteConfiguration2('斜撐')
    eq.AutomaticRebuild = False
    # Snapshot traversal is complete before any deletion.
    indices = [i for i,text in enumerate(original) if text.lstrip().startswith('"聯動')]
    for index in reversed(indices):
        count = eq.GetCount()
        assert eq.Delete(index) >= 0 and eq.GetCount() == count-1
    rewritten = [eq.Equation(i).replace('@支撐條-6.Part','@橫撐@支撐條.Part')
                 for i in range(eq.GetCount())]
    for index,text in enumerate(rewritten):eq.SetEquation(index,text)
    assert eq.GetCount() > 0, 'working equations must survive configuration creation'
    assert doc.AddConfiguration3('斜撐','','',128)
    assert doc.ConfigurationManager.ActiveConfiguration.Name == '橫撐'
    props = doc.Extension.CustomPropertyManager('斜撐')
    for key,item in diagonal_properties.items():
        if key not in ('長度','質量'):props.Add3(key,item['type'],item['get6'][1],2)
    props.Add3('驅動長度',30,'1332.097557',2)
    eq = interfaces.IEquationMgr(doc.GetEquationMgr()._oleobj_)
    while eq.GetCount():
        count = eq.GetCount()
        assert eq.Delete(count-1) >= 0 and eq.GetCount() == count-1
    mappings = {'撐寬':'驅動撐寬','翼高':'驅動翼高','唇寬':'驅動唇寬','板厚':'驅動板厚',
                '彎折半徑':'驅動彎折半徑','孔徑':'驅動孔徑','孔高':'驅動孔高','端距':'驅動端距'}
    texts = [f'"{key}" = "{value}@支撐條.Part"' for key,value in mappings.items()]
    texts += ['"D1@撐桿本體" = "驅動長度@支撐條.Part"']
    texts += [text for text in original if text.split('=',1)[0].strip().startswith('"D')
              and text.split('=',1)[0].strip() != '"D1@撐桿本體"']
    for text in texts:assert eq.Add3(-1,text,False,2,None) >= 0
    return dict(candidate_applied=True, new_configuration_inactive=True,
                original_equation_count=len(original), equation_count=eq.GetCount(),
                saved=False, geometry_verified=False)
