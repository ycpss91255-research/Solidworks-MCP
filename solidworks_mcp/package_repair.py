"""Repair private assembly copies in an explicitly owned, empty helper CAD."""
from pathlib import Path
from collections import Counter
import json,shutil
from .recovery_snapshot import get0,fingerprint,held_process
from .automation.managed_session import process_identity
from .component_states import occurrence_key,restore_suppression,missing_reference_inventory
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
    if evidence.get('source_missing_native_references'):
        key=lambda p:str(Path(p).resolve()).casefold()
        baseline={source:{key(p) for p in paths} for source,paths in evidence['source_missing_native_references'].items()}
        actual=result.get('missing_native_references_after')
        if actual is None:raise ValueError('Repair did not verify existing missing native context references')
        actual={source:{key(p) for p in paths} for source,paths in actual.items()}
        if actual!=baseline:raise ValueError('Missing native context reference inventory changed in backup')
    error=result.get('reopen_errors')
    if error!=0:
        baseline=state.get('missing_references',{})
        # SW's FileNotFound flag may already exist in the source's suppressed
        # references. Preserve that limitation, but never accept a new missing
        # path, a missing active occurrence, or a different load-error flag.
        if (error!=2 or not baseline or any(v['active'] for v in baseline.values())
                or result.get('missing_references_after')!=baseline
                or not result.get('source_missing_references_preserved')):
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

def capture_reference_aliases(app,sources):
    """Pair recorded/resolved references only when native ordering and labels agree."""
    key=lambda p:str(Path(p).resolve()).casefold()
    source_keys={key(p) for p in sources};aliases={}
    for source in sources:
        if Path(source).suffix.casefold() not in ('.sldprt','.sldasm','.slddrw'):continue
        recorded=list(app.GetDocumentDependencies2(source,False,False,False) or ())
        resolved=list(app.GetDocumentDependencies2(source,False,True,False) or ())
        if (len(recorded)%2 or len(recorded)!=len(resolved)
                or [str(n).casefold() for n in recorded[::2]]!=[str(n).casefold() for n in resolved[::2]]):
            raise RuntimeError('Cannot safely pair recorded and resolved references: '+source)
        owner={}
        for old,new in zip(recorded[1::2],resolved[1::2]):
            if key(old)==key(new) or key(old) in source_keys:continue
            if key(new) not in source_keys:continue
            if old in owner and key(owner[old])!=key(new):raise RuntimeError('Reference alias is ambiguous')
            owner[old]=new
        if owner:aliases[source]=owner
    return aliases

def capture_missing_native_references(app,sources):
    """Record already absent native context links; never treat them as copies."""
    result={}
    for source in sources:
        if Path(source).suffix.casefold() not in ('.sldprt','.sldasm','.slddrw'):continue
        refs=list(app.GetDocumentDependencies2(source,False,False,False) or ())
        if len(refs)%2:raise RuntimeError('Cannot enumerate source native references')
        missing=sorted(set(p for p in refs[1::2]
                           if Path(p).suffix.casefold() in ('.sldprt','.sldasm') and not Path(p).is_file()))
        if missing:result[source]=missing
    return result

def rebind_staged_native_references(app,evidence,verify=lambda:None):
    """Rewrite closed private files before any copied assembly is opened."""
    root,mapping,state=validate_private_package(evidence)
    key=lambda p:str(Path(p).resolve()).casefold()
    destinations={key(source):output for source,output in mapping.items()}
    missing=set(state.get('missing_references',{}))
    rewrites=[]
    for source,output in mapping.items():
        if Path(output).suffix.casefold() not in ('.sldprt','.sldasm'):continue
        verify()
        if app.GetOpenDocumentByName(output) is not None:raise RuntimeError('Reference rewrite requires a closed private file')
        refs=list(app.GetDocumentDependencies2(output,False,False,False) or ())
        absent={key(p) for p in evidence.get('source_missing_native_references',{}).get(source,[])}
        if len(refs)%2:raise RuntimeError('Cannot enumerate staged native references')
        for reference in dict.fromkeys(refs[1::2]):
            if Path(reference).suffix.casefold() in STEP_EXTENSIONS:continue
            resolved=evidence.get('native_reference_aliases',{}).get(source,{}).get(reference,reference)
            replacement=destinations.get(key(resolved))
            if replacement is None:
                if key(reference) in missing and not Path(reference).is_file():continue
                if key(reference) in absent and not Path(reference).is_file():continue
                if Path(reference).resolve().is_relative_to(root):continue
                raise RuntimeError('Staged native reference has no private replacement: '+reference)
            verify()
            if not app.ReplaceReferencedDocument(output,reference,replacement):
                raise RuntimeError('Closed private reference replacement failed: '+reference)
            rewrites.append({'document':output,'old':reference,'new':replacement})
        after=list(app.GetDocumentDependencies2(output,False,False,False) or ())
        if len(after)%2:raise RuntimeError('Cannot verify staged native references')
        for reference in after[1::2]:
            if Path(reference).suffix.casefold() in STEP_EXTENSIONS:continue
            if key(reference) in missing and not Path(reference).is_file():continue
            if key(reference) in absent and not Path(reference).is_file():continue
            if not Path(reference).resolve().is_relative_to(root):
                raise RuntimeError('Native reference still points outside private package: '+reference)
    return rewrites

def verify_closed_private_native_references(app,evidence):
    root,mapping,state=validate_private_package(evidence)
    key=lambda p:str(Path(p).resolve()).casefold()
    known_missing=set(state.get('missing_references',{}));inventory={}
    for source,output in mapping.items():
        if Path(output).suffix.casefold() not in ('.sldprt','.sldasm'):continue
        if app.GetOpenDocumentByName(output) is not None:raise RuntimeError('Final reference verification requires closed copies')
        absent={key(p) for p in evidence.get('source_missing_native_references',{}).get(source,[])}
        refs=list(app.GetDocumentDependencies2(output,False,False,False) or ())
        if len(refs)%2:raise RuntimeError('Cannot verify final native references')
        preserved=[]
        for reference in refs[1::2]:
            if Path(reference).suffix.casefold() in STEP_EXTENSIONS:continue
            ref=Path(reference)
            if not ref.is_file():
                if key(reference) not in absent|known_missing:raise RuntimeError('New missing native reference in backup: '+reference)
                preserved.append(reference)
            elif not ref.resolve().is_relative_to(root):
                raise RuntimeError('Final native reference points outside private package: '+reference)
        if preserved:inventory[source]=sorted(set(preserved))
    return inventory

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
        native_rewrites=[]
        if evidence.get('staging_method')=='copy_only':
            native_rewrites=rebind_staged_native_references(app,evidence,verify)
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
        physical={str(Path(source).resolve()).casefold():output for source,output in mapping.items()}
        missing=missing_reference_inventory(actual,exists=lambda path:Path(physical.get(path,path)).is_file())
        baseline=desired.get('missing_references',{})
        preserved=bool(baseline and missing==baseline and not any(v['active'] for v in baseline.values()))
        verify();app.CloseAllDocuments(True)
        final_missing_native=verify_closed_private_native_references(app,evidence)
        hashes={path:fingerprint(path) for path in list(mapping.values())+list(aliases)}
        if any(sha is None for sha in hashes.values()):raise RuntimeError('Repaired package file is missing')
        return {'status':'repaired','helper_pid':helper_pid,'helper_start_time':identity,
                'native_reference_rewrites':native_rewrites,
                'missing_native_references_after':final_missing_native,
                'step_aliases':aliases,'step_reference_repairs':repairs,
                'assembly_state_restoration':state_result,'saved_private_documents':saved,
                'reopen_errors':reopened[1] if isinstance(reopened,tuple) else None,
                'reopen_warnings':reopened[2] if isinstance(reopened,tuple) else None,
                'missing_references_after':missing,'source_missing_references_preserved':preserved,
                'package_files_sha256':hashes,'fresh_process_reopen':False}
