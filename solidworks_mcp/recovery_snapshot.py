"""Explicit part recovery copies; never saves the source or launches CAD."""
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,tempfile
import win32api,win32event
from .automation.managed_session import process_identity

def get0(obj,name):
    value=getattr(obj,name)
    return value() if callable(value) and not hasattr(value,'_oleobj_') else value

@contextmanager
def held_process(pid):
    handle=win32api.OpenProcess(0x100000|0x1000,False,pid)
    try:
        identity=process_identity(pid)
        if not identity or win32event.WaitForSingleObject(handle,0)!=258:
            raise RuntimeError('Snapshot target has exited')
        yield identity
    finally:handle.Close()

def fingerprint(path):
    if not path:return None
    source=Path(path)
    if not source.is_absolute():raise ValueError('Source document path must be absolute')
    digest=hashlib.sha256()
    try:
        with source.open('rb') as stream:
            for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    except FileNotFoundError:
        # A loaded part may outlive deletion/moving of its original file.
        # Preserve that absence rather than refusing its recovery copy.
        return None
    return digest.hexdigest()

class SnapshotError(RuntimeError):
    def __init__(self,message,data):
        super().__init__(message)
        self.data=data

def snapshot_part(app,pid,directory,document_adapter=lambda doc:doc,document=None):
    """Copy the current part into a unique generation, with verified state.

    A connected, PID-verified application is required. Assemblies and drawings
    are rejected because their references require separate recovery validation.
    No automatic deletion, reconnection, launch, or dialog handling occurs.
    """
    root=Path(directory)
    if not root.is_absolute():raise ValueError('Snapshot directory must be absolute')
    if not isinstance(pid,int) or pid<=0 or int(get0(app,'GetProcessID'))!=pid:
        raise ValueError('Snapshot application does not match the configured PID')
    with held_process(pid) as identity:
        raw=document if document is not None else get0(app,'ActiveDoc')
        if raw is None:raise ValueError('No active document to snapshot')
        doc=document_adapter(raw)
        if int(get0(doc,'GetType'))!=1:
            raise ValueError('Recovery snapshot currently supports parts only; no document was saved')
        before={'path':str(get0(doc,'GetPathName')),'title':str(get0(doc,'GetTitle')),
                'dirty':bool(get0(doc,'GetSaveFlag'))}
        def active_state():
            active=get0(app,'ActiveDoc')
            if active is None:return None
            active=document_adapter(active)
            return {'path':str(get0(active,'GetPathName')),'title':str(get0(active,'GetTitle')),
                    'dirty':bool(get0(active,'GetSaveFlag'))}
        active_before=active_state() if document is not None else None
        original_hash=fingerprint(before['path'])
        owner=root.resolve()/f'pid-{pid}-{hashlib.sha256(identity.encode()).hexdigest()[:12]}'
        owner.mkdir(parents=True,exist_ok=True)
        generation=Path(tempfile.mkdtemp(prefix='snapshot-',dir=owner))
        output=generation/'part.SLDPRT'
        manifest=generation/'manifest.json'
        evidence={'status':'writing','pid':pid,'process_start_time':identity,
                  'created_at':datetime.now(timezone.utc).isoformat(),'source':before,
                  'source_sha256':original_hash,'snapshot_path':str(output),
                  'manifest_path':str(manifest),'document_type':'part'}
        if document is not None:evidence['active_before']=active_before
        def record():
            temporary=generation/'manifest.tmp'
            temporary.write_text(json.dumps(evidence,indent=2,ensure_ascii=False),encoding='utf-8')
            temporary.replace(manifest)
        record()
        try:
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('Snapshot target identity changed before save')
            # swSaveAsOptions_Silent (1) | swSaveAsOptions_Copy (2).
            # Do not use SaveReferenced or a fallback Save/SaveAs operation.
            status=doc.SaveAs3(str(output),0,3)
            evidence['save_status']=status
            after={'path':str(get0(doc,'GetPathName')),'title':str(get0(doc,'GetTitle')),
                   'dirty':bool(get0(doc,'GetSaveFlag'))}
            evidence['source_after']=after
            if document is not None:
                evidence['active_after']=active_state()
                if evidence['active_after']!=active_before:
                    raise RuntimeError('Active document changed during background snapshot')
            if status!=0 or not output.is_file() or output.stat().st_size==0:
                raise RuntimeError(f'Recovery copy failed (save status {status})')
            if after!=before or fingerprint(before['path'])!=original_hash:
                raise RuntimeError('Source document state or saved file changed during snapshot')
            if int(get0(app,'GetProcessID'))!=pid or process_identity(pid)!=identity:
                raise RuntimeError('Snapshot target identity changed after save')
            evidence.update(status='complete',snapshot_bytes=output.stat().st_size,
                            snapshot_sha256=fingerprint(str(output)),source_preserved=True)
            record()
            return evidence
        except Exception as exc:
            evidence.update(status='failed',error=str(exc))
            record()
            raise SnapshotError(str(exc),evidence) from exc
