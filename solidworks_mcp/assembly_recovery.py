"""Experimental saved CAD packages with source preservation checks."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,tempfile,uuid
from .recovery_snapshot import get0,held_process,fingerprint,SnapshotError
from .automation.managed_session import process_identity

def document_state(doc):
    return {'path':str(get0(doc,'GetPathName')),'title':str(get0(doc,'GetTitle')),
            'dirty':bool(get0(doc,'GetSaveFlag'))}

def snapshot_package(app,pid,directory,document_adapter=lambda doc:doc,pack_factory=None,allowed_types=(2,3),document=None):
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
            from .native_pack import NativePack
            major=int(str(get0(app,'RevisionNumber')).split('.')[0])
            pack_factory=lambda doc:NativePack(doc,major)
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
        # Non-CAD dependencies need separate restoration validation.
        unsupported=[p for p in paths if path_key(p)!=source_key and Path(p).suffix.casefold() not in ('.sldprt','.sldasm')]
        if unsupported:
            raise ValueError('Experimental package recovery supports saved part and assembly references only; '
                             f'unsupported references for {before["path"]}: {unsupported}')
        sources={p:fingerprint(p) for p in paths}
        if any(value is None for value in sources.values()):
            raise ValueError('Package contains missing or unsaved source files')
        def loaded_states():
            result={}
            for path in paths:
                loaded=app.GetOpenDocumentByName(path)
                result[path]=document_state(document_adapter(loaded)) if loaded is not None else None
            return result
        loaded_before=loaded_states()
        owner=root.resolve()/f'pid-{pid}-{hashlib.sha256(identity.encode()).hexdigest()[:12]}'
        owner.mkdir(parents=True,exist_ok=True)
        generation=Path(tempfile.mkdtemp(prefix=document_type+'-',dir=owner))
        manifest=generation/'manifest.json'
        evidence={'status':'writing','pid':pid,'process_start_time':identity,
                  'created_at':datetime.now(timezone.utc).isoformat(),'document_type':document_type,
                  'source':before,'source_files_sha256':sources,'loaded_sources':loaded_before,
                  'manifest_path':str(manifest),'validated_scope':'saved '+document_type+' with saved part and assembly references'}
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
            for path in outputs:
                destination=Path(path)
                if (not destination.is_absolute() or not destination.resolve().is_relative_to(generation.resolve())
                        or destination.exists() or path_key(destination) in {path_key(p) for p in paths}):
                    raise RuntimeError('Package destination is not a new private file')
            mapping=dict(zip(paths,map(str,outputs)))
            evidence['package_files']=mapping
            evidence['snapshot_path']=next(mapping[p] for p in paths if path_key(p)==source_key)
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('Snapshot target identity changed before save')
            statuses=pack.save();evidence['save_statuses']=statuses
            if len(statuses)!=len(paths) or any(statuses):raise RuntimeError('Pack and Go save failed')
            if any(not Path(p).is_file() or Path(p).stat().st_size==0 for p in outputs):
                raise RuntimeError('Package output is missing or empty')
            after=document_state(doc);evidence['source_after']=after
            if document is not None:
                evidence['active_after']=active_state()
                if evidence['active_after']!=active_before:
                    raise RuntimeError('Active document changed during background package')
            if (after!=before or loaded_states()!=loaded_before
                    or any(fingerprint(p)!=sha for p,sha in sources.items())):
                raise RuntimeError('Source state or disk files changed during assembly snapshot')
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('Snapshot target identity changed after save')
            evidence.update(status='complete',source_preserved=True,
                            package_files_sha256={p:fingerprint(p) for p in outputs})
            record();return evidence
        except Exception as exc:
            evidence.update(status='failed',error=str(exc));record()
            raise SnapshotError(str(exc),evidence) from exc

def snapshot_assembly(app,pid,directory,document_adapter=lambda doc:doc,pack_factory=None):
    return snapshot_package(app,pid,directory,document_adapter,pack_factory,allowed_types=(2,))
