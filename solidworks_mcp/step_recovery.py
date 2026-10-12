"""Rewrite resolved STEP links in private copies, never in source documents."""
from pathlib import Path
import tempfile
from .recovery_snapshot import get0,held_process
from .assembly_recovery import document_state,STEP_EXTENSIONS
from .automation.managed_session import process_identity

def repair_step_links(app,pid,generation,mapping,adapter,allow_activation=False,idle=lambda:True):
    root=Path(generation).resolve()
    outputs={str(Path(p).resolve()).casefold() for p in mapping.values()}
    steps={str(Path(p).resolve()).casefold() for p in mapping.values()
           if Path(p).suffix.casefold() in STEP_EXTENSIONS}
    if any(not Path(p).resolve().is_relative_to(root) for p in mapping.values()):
        raise ValueError('STEP repair outputs must be private')
    repaired=[]
    with held_process(pid) as identity:
        def verify():
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('STEP repair target identity changed')
            if not idle():raise RuntimeError('STEP repair interrupted by a command or dialog')
        def references(path,search):
            values=list(app.GetDocumentDependencies2(str(path),False,search,False) or ())
            if len(values)%2:raise RuntimeError('Cannot verify STEP reference list')
            return [p for p in values[1::2] if Path(p).suffix.casefold() in STEP_EXTENSIONS]
        def active():
            doc=get0(app,'ActiveDoc')
            return document_state(adapter(doc)) if doc is not None else None
        for output in mapping.values():
            if Path(output).suffix.casefold() not in ('.sldprt','.sldasm'):continue
            verify();recorded=references(output,False)
            if not recorded or all(str(Path(p).resolve()).casefold() in steps for p in recorded):continue
            if Path(output).suffix.casefold()!='.sldprt':
                raise RuntimeError('STEP assembly reference repair is not validated')
            if not allow_activation:
                raise RuntimeError('STEP copy repair requires enabled temporary API activation')
            resolved=references(output,True)
            if len(resolved)!=len(recorded) or any(str(Path(p).resolve()).casefold() not in steps for p in resolved):
                raise RuntimeError('STEP copies do not resolve entirely inside this package')
            if app.GetOpenDocumentByName(str(output)) is not None:
                raise RuntimeError('Private repair document is already open; refusing to take it over')
            before=active();opened=None;temporary=None
            try:
                verify()
                result=app.OpenDoc6(str(output),1,3,'',0,0)  # Silent | ReadOnly.
                raw=result[0] if isinstance(result,tuple) else result
                if raw is None:raise RuntimeError('Cannot open private STEP owner read-only')
                opened=adapter(raw)
                if str(Path(get0(opened,'GetPathName')).resolve()).casefold()!=str(Path(output).resolve()).casefold():
                    opened=None
                    raise RuntimeError('STEP repair opened a different document; it was not closed or saved')
                fd,name=tempfile.mkstemp(prefix='sr-',suffix='.SLDPRT',dir=Path(output).parent)
                import os
                os.close(fd);temporary=Path(name);temporary.unlink()
                verify()
                status=opened.SaveAs3(str(temporary),0,3)  # Silent | Copy.
                if status!=0 or not temporary.is_file() or not temporary.stat().st_size:
                    raise RuntimeError('STEP owner recovery rewrite failed')
                actual=references(temporary,False)
                if len(actual)!=len(recorded) or any(str(Path(p).resolve()).casefold() not in steps for p in actual):
                    raise RuntimeError('Saved STEP owner still refers outside the package')
            finally:
                if opened is not None:
                    verify()
                    current=active()
                    own=document_state(opened)
                    if current not in (before,own,None):
                        raise RuntimeError('Active document changed externally during STEP repair')
                    app.CloseDoc(get0(opened,'GetTitle'))
                    if before is not None and active()!=before:
                        app.ActivateDoc3(before['title'],False,1,0)
                    if active()!=before:raise RuntimeError('STEP repair did not restore the active document')
            verify()
            # Only replace a closed, validated private output. Assembly links
            # keep the package filename; SaveAs Copy preserves native identity.
            if str(Path(output).resolve()).casefold() not in outputs:
                raise RuntimeError('STEP repair destination changed')
            temporary.replace(output)
            repaired.append({'document':str(output),'recorded_before':recorded,'recorded_after':actual})
        verify()
    return repaired
