"""Experimental saved CAD packages with source preservation checks."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,tempfile,uuid
from .recovery_snapshot import get0,held_process,fingerprint,SnapshotError
from .automation.managed_session import process_identity

STEP_EXTENSIONS={'.step','.stp'}

def document_state(doc):
    return {'path':str(get0(doc,'GetPathName')),'title':str(get0(doc,'GetTitle')),
            'dirty':bool(get0(doc,'GetSaveFlag'))}

def snapshot_package(app,pid,directory,document_adapter=lambda doc:doc,pack_factory=None,allowed_types=(2,3),document=None,
                     allow_step_activation=False,idle=lambda:True,state_reader=None,package_processor=None):
    root=Path(directory)
    if not root.is_absolute():raise ValueError('Snapshot directory must be absolute')
    if not isinstance(pid,int) or pid<=0 or int(get0(app,'GetProcessID'))!=pid:
        raise ValueError('Snapshot application does not match the configured PID')
    with held_process(pid) as identity:
        raw=document if document is not None else get0(app,'ActiveDoc')
        if raw is None:raise ValueError('No active document to package')
        doc=document_adapter(raw)
        kind=int(get0(doc,'GetType'))
        if kind not in allowed_types:raise ValueError('Package recovery requires a supported assembly or drawing')
        document_type='drawing' if kind==3 else 'assembly'
        before=document_state(doc)
        def active_state():
            current=get0(app,'ActiveDoc')
            return document_state(document_adapter(current)) if current is not None else None
        active_before=active_state() if document is not None else None
        if not before['path'] or fingerprint(before['path']) is None:
            raise ValueError('Package recovery requires an existing saved source document')
        expected_suffix='.slddrw' if kind==3 else '.sldasm'
        if Path(before['path']).suffix.casefold()!=expected_suffix:
            raise ValueError('Source filename does not match its CAD document type')
        if pack_factory is None:
            if package_processor is None:
                raise ValueError('Safe native package recovery requires an independently configured repair helper')
            from .native_pack import NativePack
            major=int(str(get0(app,'RevisionNumber')).split('.')[0])
            pack_factory=lambda doc:NativePack(doc,major,app,document_adapter)
            if kind==2 and state_reader is None:
                from .component_states import capture_assembly_state
                state_reader=lambda model:capture_assembly_state(model,major)
        assembly_state=state_reader(doc) if state_reader is not None else None
        pack=pack_factory(doc)
        raw_paths=pack.documents()
        if any(not Path(path).is_absolute() for path in raw_paths):
            raise ValueError('Package source paths must be absolute')
        paths=list(map(str,raw_paths))
        path_key=lambda path:str(Path(path).resolve()).casefold()
        if not paths or len({path_key(p) for p in paths})!=len(paths):
            raise ValueError('Package source list is empty or ambiguous')
        source_key=path_key(before['path'])
        if source_key not in {path_key(p) for p in paths}:
            raise ValueError('Package does not include its active source document')
        # Include the STEP source dependencies exposed by 3D Interconnect.
        supported={'.sldprt','.sldasm'}|STEP_EXTENSIONS
        unsupported=[p for p in paths if path_key(p)!=source_key and Path(p).suffix.casefold() not in supported]
        if unsupported:
            raise ValueError('Experimental package recovery supports saved part and assembly references only; '
                             f'unsupported references for {before["path"]}: {unsupported}')
        sources={p:fingerprint(p) for p in paths}
        if any(value is None for value in sources.values()):
            raise ValueError('Package contains missing or unsaved source files')
        native_aliases={};native_missing={}
        if hasattr(pack,'app'):
            from .package_repair import capture_reference_aliases,capture_missing_native_references
            native_aliases=capture_reference_aliases(app,paths)
            native_missing=capture_missing_native_references(app,paths)
        def loaded_states():
            result={}
            for path in paths:
                loaded=app.GetOpenDocumentByName(path)
                result[path]=document_state(document_adapter(loaded)) if loaded is not None else None
            return result
        loaded_before=loaded_states()
        step_sources=[p for p in paths if Path(p).suffix.casefold() in STEP_EXTENSIONS]
        if any(loaded_before[p] and loaded_before[p]['dirty'] for p in step_sources):
            raise ValueError('Dirty STEP documents require a native recovery copy; refusing a saved-baseline-only package')
        # Short names preserve room for native Pack and Go's source hierarchy.
        # Ownership still includes both PID and creation time in the digest and
        # full manifest; folders are separate under each session's private root.
        owner=root.resolve()/('p'+hashlib.sha256(f'{pid}:{identity}'.encode()).hexdigest()[:10])
        owner.mkdir(parents=True,exist_ok=True)
        generation=Path(tempfile.mkdtemp(prefix=document_type[0],dir=owner))
        manifest=generation/'manifest.json'
        evidence={'status':'writing','pid':pid,'process_start_time':identity,
                  'created_at':datetime.now(timezone.utc).isoformat(),'document_type':document_type,
                  'source':before,'source_files_sha256':sources,'loaded_sources':loaded_before,
                  'manifest_path':str(manifest),'validated_scope':'saved '+document_type+' with saved part/assembly references and byte-identical STEP dependencies'}
        evidence['step_source_files']=step_sources
        if native_aliases:evidence['native_reference_aliases']=native_aliases
        if native_missing:
            evidence['source_missing_native_references']=native_missing
            evidence['source_limitations']={'missing_native_context_references':native_missing}
        if assembly_state is not None:evidence['assembly_occurrence_state']=assembly_state
        if document is not None:evidence['active_before']=active_before
        def record():
            temporary=generation/'manifest.tmp'
            temporary.write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf-8')
            temporary.replace(manifest)
        record()
        try:
            outputs=pack.destinations(generation,'r'+uuid.uuid4().hex[:8]+'-')
            if len(outputs)!=len(paths) or len({str(p).casefold() for p in outputs})!=len(outputs):
                raise RuntimeError('Package destinations are incomplete or collide')
            from .private_paths import canonical_outputs
            canonical=canonical_outputs(outputs)
            source_keys={path_key(p) for p in paths}
            for path,resolved in zip(outputs,canonical):
                destination=Path(path)
                if (not destination.is_absolute() or not resolved.is_relative_to(generation.resolve())
                        or destination.exists() or str(resolved).casefold() in source_keys):
                    raise RuntimeError('Package destination is not a new private file')
            mapping=dict(zip(paths,map(str,outputs)))
            evidence['package_files']=mapping
            if hasattr(pack,'app'):evidence['staging_method']='copy_only'
            evidence['snapshot_path']=next(mapping[p] for p in paths if path_key(p)==source_key)
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('Snapshot target identity changed before save')
            statuses=pack.save();evidence['save_statuses']=statuses
            # SW2023's real mixed package returned only native-document codes,
            # while also copying its three STEP sources. File completeness and
            # STEP content are independently mandatory below.
            allowed_counts={len(paths),len(paths)-len(step_sources)}
            if len(statuses) not in allowed_counts or any(statuses):raise RuntimeError('Pack and Go save failed')
            evidence['save_status_count']=len(statuses)
            if any(not Path(p).is_file() or Path(p).stat().st_size==0 for p in outputs):
                raise RuntimeError('Package output is missing or empty')
            for source in step_sources:
                if fingerprint(mapping[source])!=sources[source]:
                    raise RuntimeError('STEP dependency copy does not match its saved source')
            if package_processor is not None:
                # The processor has its own configured helper; it must not
                # repair in, retarget or finalize this source application's PID.
                record()
                proof=package_processor(evidence)
                from .package_repair import validate_repair_result
                validate_repair_result(evidence,proof)
                evidence['independent_package_repair']=proof
                if proof.get('source_missing_references_preserved'):
                    evidence.setdefault('source_limitations',{})['missing_suppressed_references']=assembly_state['missing_references']
            if step_sources:
                # A copied STEP is insufficient if a saved import still points
                # to the original. Search=False reads recorded paths, rather
                # than masking them through SolidWorks' reference search rules.
                leaks=[]
                for source,output in mapping.items():
                    if Path(source).suffix.casefold() not in ('.sldprt','.sldasm'):continue
                    references=list(app.GetDocumentDependencies2(output,False,False,False) or ())
                    if len(references)%2:raise RuntimeError('Cannot verify recorded STEP dependency list')
                    for reference in references[1::2]:
                        if Path(reference).suffix.casefold() in STEP_EXTENSIONS and not Path(reference).resolve().is_relative_to(generation.resolve()):
                            leaks.append({'document':output,'reference':reference})
                evidence['unresolved_step_references']=leaks
                if leaks and allow_step_activation and package_processor is None:
                    from .step_recovery import repair_step_links
                    evidence['step_reference_repairs']=repair_step_links(app,pid,generation,mapping,
                        document_adapter,allow_activation=True,idle=idle)
                    leaks=[]
                    for source,output in mapping.items():
                        if Path(source).suffix.casefold() not in ('.sldprt','.sldasm'):continue
                        references=list(app.GetDocumentDependencies2(output,False,False,False) or ())
                        if len(references)%2:raise RuntimeError('Cannot verify repaired STEP dependency list')
                        for reference in references[1::2]:
                            if Path(reference).suffix.casefold() in STEP_EXTENSIONS and not Path(reference).resolve().is_relative_to(generation.resolve()):
                                leaks.append({'document':output,'reference':reference})
                    evidence['unresolved_step_references']=leaks
                if leaks:raise RuntimeError('Copied STEP references still point outside the private package; recovery is incomplete')
            after=document_state(doc);evidence['source_after']=after
            if state_reader is not None:
                state_after=state_reader(doc)
                evidence['assembly_occurrence_state_after']=state_after
                if state_after!=assembly_state:
                    raise RuntimeError('Assembly occurrence configuration, placement or suppression changed during snapshot')
            if document is not None:
                evidence['active_after']=active_state()
                if evidence['active_after']!=active_before:
                    raise RuntimeError('Active document changed during background package')
            if (after!=before or loaded_states()!=loaded_before
                    or any(fingerprint(p)!=sha for p,sha in sources.items())):
                raise RuntimeError('Source state or disk files changed during assembly snapshot')
            if hasattr(pack,'app') and capture_missing_native_references(app,paths)!=native_missing:
                raise RuntimeError('Source missing native reference inventory changed during snapshot')
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('Snapshot target identity changed after save')
            evidence.update(status='complete',source_preserved=True,
                            package_files_sha256={p:fingerprint(p) for p in outputs})
            if package_processor is not None:
                evidence['package_files_sha256']=validate_repair_result(evidence,proof)
            record();return evidence
        except Exception as exc:
            evidence.update(status='failed',error=str(exc));record()
            raise SnapshotError(str(exc),evidence) from exc

def snapshot_assembly(app,pid,directory,document_adapter=lambda doc:doc,pack_factory=None):
    return snapshot_package(app,pid,directory,document_adapter,pack_factory,allowed_types=(2,))
