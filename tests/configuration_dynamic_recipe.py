"""Opt-in private rack fixture recipes. No connection, launch, save or close.

Invoke through an existing owned PID-bound MCP, using typed interfaces.
These are model-specific regression recipes, not automatic production repair.
"""
from pathlib import Path


def _preflight(sw, m, fixture_dir, expected_pid):
    assert type(expected_pid) is int and expected_pid > 0
    assert sw.GetProcessID() == expected_pid, 'PID mismatch'
    private=Path(fixture_dir)
    assert private.is_absolute(), 'absolute private fixture required'
    private=private.resolve()
    paths=[m.IModelDoc2(raw._oleobj_).GetPathName() for raw in sw.GetDocuments() or []]
    assert paths and all(p and Path(p).resolve().is_relative_to(private) for p in paths), 'non-private document'
    return private

def restore_binding(sw, m, fixture_dir, expected_pid):
    private=_preflight(sw,m,fixture_dir,expected_pid)
    import json
    assert all(Path(m.IModelDoc2(x._oleobj_).GetPathName()).is_relative_to(private) for x in sw.GetDocuments() or [])
    frame=m.IModelDoc2(sw.GetOpenDocumentByName(str(private/'支架.SLDASM'))._oleobj_)
    assembly=m.IAssemblyDoc(frame._oleobj_)
    assert sw.ActivateDoc3(frame.GetTitle(),False,0,0)[0]
    eq=m.IEquationMgr(frame.GetEquationMgr()._oleobj_)
    eq.AutomaticRebuild=False
    seed=next(m.IComponent2(raw._oleobj_) for raw in assembly.GetComponents(True) if m.IComponent2(raw._oleobj_).Name2=='支撐條-1')
    # Re-resolve the existing seed against the recreated configuration; own copy only.
    seed.ReferencedConfiguration='斜撐'
    seed.SetSuppression2(2)
    assert seed.GetModelDoc2()
    texts=['"斜撐端距" = "驅動端距@支撐條-1.Part"','"斜撐長度" = sqr("撐孔水平跨距"^2 + "斜撐段高"^2) + 2*"斜撐端距"','"支撐條<1>" = iif("輸入有效"=0,"suppressed","unsuppressed")']
    for text in texts:
     lhs=text.split('=',1)[0].strip()
     indices=[i for i in range(eq.GetCount()) if eq.Equation(i).split('=',1)[0].strip()==lhs]
     assert len(indices)<=1,('duplicate parent equations',lhs)
     if indices:eq.SetEquation(indices[0],text)
     else:assert eq.Add2(-1,text,False)>=0
    eq.EvaluateAll()
    frame.ClearSelection2(True)
    assert seed.Select4(False,None,False)
    assert assembly.EditPart2(True,False,0)==0
    try:
     brace=m.IModelDoc2(seed.GetModelDoc2()._oleobj_)
     assert brace.ConfigurationManager.ActiveConfiguration.Name=='斜撐'
     part_eq=m.IEquationMgr(brace.GetEquationMgr()._oleobj_)
     index=next(i for i in range(part_eq.GetCount()) if part_eq.Equation(i).split('=',1)[0].strip()=='"D1@撐桿本體"')
     assert part_eq.SetEquationAndConfigurationOption(index,'"D1@撐桿本體" = "斜撐長度@支架.Assembly"',1,None)>=0
     part_eq.AutomaticRebuild=True;part_eq.AutomaticSolveOrder=True
    finally:
     assembly.EditAssembly();frame.ClearSelection2(True)
    eq.AutomaticRebuild=True;eq.AutomaticSolveOrder=True
    eq.EvaluateAll()
    rebuilt=frame.ForceRebuild3(False)
    result={'frame_rebuilt':bool(rebuilt),'diagonal_seed_loaded':bool(seed.GetModelDoc2()),'equations_restored':texts,'part_length_binding_restored':True}
    assert rebuilt,result

    return result

def verify_changed_input(sw, m, fixture_dir, expected_pid):
    private=_preflight(sw,m,fixture_dir,expected_pid)
    import json, math
    from solidworks_mcp.diagnostics.configuration_acceptance import observe_configuration, assert_geometry
    assert all(Path(m.IModelDoc2(x._oleobj_).GetPathName()).is_relative_to(private) for x in sw.GetDocuments() or [])
    frame=m.IModelDoc2(sw.GetOpenDocumentByName(str(private/'支架.SLDASM'))._oleobj_)
    part=m.IModelDoc2(sw.GetOpenDocumentByName(str(private/'支撐條.SLDPRT'))._oleobj_)
    props=frame.Extension.CustomPropertyManager('Default')
    original=props.Get6('驅動最大段高',False)[1]
    assert float(original)==800.,original
    rows=[]
    try:
     for maximum in (700.,800.):
      assert sw.ActivateDoc3(frame.GetTitle(),False,0,0)[0]
      props.Add3('驅動最大段高',30,str(maximum),2)
      eq=m.IEquationMgr(frame.GetEquationMgr()._oleobj_)
      eq.EvaluateAll()
      rebuilt=bool(frame.ForceRebuild3(False))
      assert rebuilt,('parent rebuild failed',maximum)
      expected_height=3200./math.ceil(3200./maximum)
      expected_span=math.hypot(1040.,expected_height)
      assert sw.ActivateDoc3(part.GetTitle(),False,0,0)[0]
      for cfg,length,span in [('橫撐',1070.,1040.),('斜撐',expected_span+20.,expected_span)]:
       part.ShowConfiguration2(cfg)
       rebuilt=bool(part.ForceRebuild3(False))
       observation=observe_configuration(sw,str(private/'支撐條.SLDPRT'),str(private),sw.GetProcessID(),rebuilt)
       row={'maximum_segment_mm':maximum,'observation':observation}
       rows.append(row)
       (private/'at-dynamic-observations.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
       assert_geometry(observation,{'configuration':cfg,'length_mm':length,'hole_span_mm':span,'equation_count':18})
    finally:
     props.Add3('驅動最大段高',30,original,2)
    result=rows

    return result

