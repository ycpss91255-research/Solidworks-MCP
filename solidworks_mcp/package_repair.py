"""Repair private assembly copies in an explicitly owned, empty helper CAD."""
from pathlib import Path
from collections import Counter
import json,shutil
from .recovery_snapshot import get0,fingerprint,held_process
from .automation.managed_session import process_identity
from .component_states import occurrence_key,restore_suppression
from .step_recovery import repair_step_links
from .assembly_recovery import STEP_EXTENSIONS

def validate_private_package(evidence):
    manifest=Path(evidence['manifest_path'])
    if not manifest.is_absolute():raise ValueError('Package manifest must be absolute')
    root=manifest.parent.resolve()
    mapping=evidence['package_files']
    if not mapping:raise ValueError('Private package must contain files')
    outputs=set()
    sources={str(Path(p).resolve()).casefold() for p in mapping}
    for source,output in mapping.items():
        path=Path(output);key=str(path.resolve()).casefold()
        if (not Path(source).is_absolute() or not path.is_absolute()
                or not path.resolve().is_relative_to(root) or key in sources
                or key in outputs or not path.is_file() or not path.stat().st_size):
            raise ValueError('Package contains a non-private, missing or ambiguous output')
        outputs.add(key)
    snapshot=Path(evidence['snapshot_path'])
    if (str(snapshot.resolve()).casefold() not in outputs
            or snapshot.suffix.casefold()!='.sldasm'):
        raise ValueError('Repair requires a packaged assembly root')
    state=evidence['assembly_occurrence_state']
    if not isinstance(state['configuration'],str):raise ValueError('Invalid source configuration')
    for row in state['occurrences']:occurrence_key(row)
    return root,mapping,state

def materialize_step_aliases(app,evidence):
    root,mapping,_=validate_private_package(evidence)
    primaries={source:output for source,output in mapping.items()
               if Path(source).suffix.casefold() in STEP_EXTENSIONS}
    aliases={}
    for source,output in primaries.items():
        expected=evidence['source_files_sha256'][source]
        if not expected or fingerprint(output)!=expected:
            raise ValueError('Private STEP primary does not match its source hash')
    for output in mapping.values():
        if Path(output).suffix.casefold() not in ('.sldprt','.sldasm'):continue
        references=list(app.GetDocumentDependencies2(output,False,False,False) or ())
        if len(references)%2:raise ValueError('Invalid recorded dependency list')
        for reference in references[1::2]:
            ref=Path(reference)
            if ref.suffix.casefold() not in STEP_EXTENSIONS:continue
            exact=[s for s in primaries if Path(s).resolve()==ref.resolve()]
            candidates=exact or [s for s in primaries if Path(s).name.casefold()==ref.name.casefold()]
            if len(candidates)!=1:raise ValueError('STEP reference has no unique package primary')
            primary=primaries[candidates[0]]
            expected=evidence['source_files_sha256'][candidates[0]]
            # Place the original STEP basename beside its native owner so an
            # empty helper can resolve it without a loaded-source cache.
            alias=Path(output).parent/ref.name
            if not alias.resolve().is_relative_to(root):raise ValueError('STEP alias escapes package')
            if alias.exists():
                if fingerprint(str(alias))!=expected:raise ValueError('STEP alias collision or modified content')
            else:
                # Exclusive creation prevents clobbering an intervening file.
                with open(primary,'rb') as src,alias.open('xb') as dst:shutil.copyfileobj(src,dst)
            if fingerprint(str(alias))!=expected:raise ValueError('STEP alias hash mismatch')
            aliases[str(alias)]={'primary':primary,'sha256':expected}
    return aliases

def validate_repair_result(evidence,result):
    root,mapping,state=validate_private_package(evidence)
    if (result.get('status')!='repaired' or int(result.get('helper_pid',0))<=0
            or int(result['helper_pid'])==int(evidence['pid'])
            or not result.get('helper_start_time')):
        raise ValueError('Repair result has no independent helper identity')
    if result.get('assembly_state_restoration',{}).get('verified_occurrences')!=len(state['occurrences']):
        raise ValueError('Repair result did not verify every assembly occurrence')
    if result.get('reopen_errors')!=0:
        raise ValueError('Repair reopen has unresolved load errors; source owner cannot finalize the backup')
    hashes=result.get('package_files_sha256',{})
    required=set(mapping.values())
    for alias,details in result.get('step_aliases',{}).items():
        if not Path(alias).resolve().is_relative_to(root) or details['primary'] not in mapping.values():
            raise ValueError('Repair alias is not private or has no package primary')
        sources=[s for s,d in mapping.items() if d==details['primary'] and Path(s).suffix.casefold() in STEP_EXTENSIONS]
        if len(sources)!=1 or details['sha256']!=evidence['source_files_sha256'][sources[0]]:
            raise ValueError('Repair alias does not match its original STEP source')
        if fingerprint(alias)!=details['sha256']:raise ValueError('Repair alias content changed')
        required.add(alias)
    if set(hashes)!=required:raise ValueError('Repair hash inventory is incomplete or includes undeclared files')
    if any(not sha or fingerprint(path)!=sha for path,sha in hashes.items()):
        raise ValueError('Repaired package content changed')
    return hashes

def repair_private_assembly(app,helper_pid,helper_session_file,evidence,module,
                            memory_warning_action='cancel',verify_source=lambda:None):
    """Return repair evidence only; the source owner finalizes its own manifest."""
    root,mapping,desired=validate_private_package(evidence)
    session=Path(helper_session_file)
    if not session.is_absolute():raise ValueError('Helper requires an absolute owned session file')
    owner=json.loads(session.read_text(encoding='utf-8'))
    if owner.get('role')!='recovery_repair' or int(owner['pid'])!=helper_pid:
        raise ValueError('Session is not this dedicated recovery helper')
    if helper_pid==int(evidence['pid']):raise ValueError('Repair helper must be separate from source CAD')
    from .recovery_monitor import visible_dialog
    from .automation.memory_warning import MemoryWarningHandler
    with held_process(helper_pid) as identity:
        def verify():
            if (owner['start_time']!=identity or process_identity(helper_pid)!=identity
                    or int(get0(app,'GetProcessID'))!=helper_pid):
                raise RuntimeError('Repair helper identity changed')
            if app.CommandInProgress or visible_dialog(helper_pid):
                raise RuntimeError('Repair helper has a command or dialog')
            verify_source()
        verify()
        if get0(app,'GetDocuments') or ():
            raise RuntimeError('Repair helper is not empty; no documents were closed')
        app.DocumentVisible(False,1);app.DocumentVisible(False,2)
        aliases=materialize_step_aliases(app,evidence)
        allowed=dict(mapping)
        allowed.update({path:path for path in aliases})
        adapter=lambda d:module.IModelDoc2(d._oleobj_)
        def idle():verify();return True
        repairs=repair_step_links(app,helper_pid,root,allowed,adapter,
                                  allow_activation=True,idle=idle)
        def open_root(flags):
            verify()
            with MemoryWarningHandler(helper_pid,memory_warning_action,60):
                result=app.OpenDoc6(evidence['snapshot_path'],2,flags,'',0,0)
            raw=result[0] if isinstance(result,tuple) else result
            if raw is None:raise RuntimeError('Private assembly open was canceled or failed')
            doc=adapter(raw)
            if Path(get0(doc,'GetPathName')).resolve()!=Path(evidence['snapshot_path']).resolve():
                raise RuntimeError('Helper opened another model; it was not saved or closed')
            app.ActivateDoc3(get0(doc,'GetTitle'),False,1,0)
            current=get0(get0(doc.ConfigurationManager,'ActiveConfiguration'),'Name')
            if current!=desired['configuration']:
                doc.ShowConfiguration2(desired['configuration'])
                current=get0(get0(doc.ConfigurationManager,'ActiveConfiguration'),'Name')
            if current!=desired['configuration']:
                raise RuntimeError('Private assembly lacks the source configuration')
            return doc,result
        reverse={str(Path(v).resolve()).casefold():str(Path(k).resolve()).casefold()
                 for k,v in mapping.items()}
        def read(component):
            path=get0(component,'GetPathName');key=str(Path(path).resolve()).casefold() if path else ''
            transform=get0(component,'Transform2')
            return {'source_path':reverse.get(key,key),
                    'matrix':list(get0(transform,'ArrayData')) if transform is not None else None,
                    'suppressed':bool(component.IsSuppressed())}
        def components(doc):
            return [module.IComponent2(c._oleobj_) for c in module.IAssemblyDoc(doc._oleobj_).GetComponents(False) or ()]
        def write(component,suppressed):
            if not Path(get0(component,'GetPathName')).resolve().is_relative_to(root):
                raise RuntimeError('Cannot change a component outside the private package')
            parent=get0(component,'GetParent')
            if parent is not None:
                parent=module.IComponent2(parent._oleobj_);raw=get0(parent,'GetModelDoc2')
                if raw is None or not Path(get0(adapter(raw),'GetPathName')).resolve().is_relative_to(root):
                    raise RuntimeError('Cannot change a parent outside the private package')
            component.SetSuppression2(0 if suppressed else 2)
        doc,opened=open_root(1)
        state_result=restore_suppression(components(doc),desired['occurrences'],read,write,verify)
        saved=[]
        for raw in get0(app,'GetDocuments') or ():
            model=adapter(raw);path=get0(model,'GetPathName')
            if bool(get0(model,'GetSaveFlag')) or Path(path).resolve()==Path(evidence['snapshot_path']).resolve():
                verify()
                if not Path(path).resolve().is_relative_to(root):raise RuntimeError('Helper save is not private')
                if model.SaveAs3(path,0,1)!=0:raise RuntimeError('Private assembly state save failed')
                saved.append(path)
        verify();app.CloseAllDocuments(True)
        doc,reopened=open_root(3)
        actual=[read(c) for c in components(doc)]
        def full_key(row):return occurrence_key(row),row['suppressed']
        if Counter(map(full_key,actual))!=Counter(map(full_key,desired['occurrences'])):
            raise RuntimeError('Saved private assembly state did not survive reopening')
        verify();app.CloseAllDocuments(True)
        hashes={path:fingerprint(path) for path in list(mapping.values())+list(aliases)}
        if any(sha is None for sha in hashes.values()):raise RuntimeError('Repaired package file is missing')
        return {'status':'repaired','helper_pid':helper_pid,'helper_start_time':identity,
                'step_aliases':aliases,'step_reference_repairs':repairs,
                'assembly_state_restoration':state_result,'saved_private_documents':saved,
                'reopen_errors':reopened[1] if isinstance(reopened,tuple) else None,
                'reopen_warnings':reopened[2] if isinstance(reopened,tuple) else None,
                'package_files_sha256':hashes,'fresh_process_reopen':False}
