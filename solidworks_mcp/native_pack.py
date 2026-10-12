"""Pack and Go through the installed native interface of an existing COM object."""
from pathlib import Path

def native_extension(extension,major):
    import ctypes,pythoncom,comtypes,comtypes.client
    from .utils import find_solidworks
    executable=find_solidworks()
    if not executable:raise RuntimeError('Installed SolidWorks type library not found')
    typelib=Path(executable).parent/'sldworks.tlb'
    if pythoncom.LoadTypeLib(str(typelib)).GetLibAttr()[3]!=major:
        raise RuntimeError('Installed native type library does not match the connected CAD version')
    module=comtypes.client.GetModule(str(typelib))
    stream=pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch,extension._oleobj_)
    stream.Seek(0,0);blob=stream.Read(65536)
    sh=ctypes.WinDLL('shlwapi')
    sh.SHCreateMemStream.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    sh.SHCreateMemStream.restype=ctypes.c_void_p
    buffer=ctypes.create_string_buffer(blob)
    address=sh.SHCreateMemStream(buffer,len(blob))
    if not address:
        stream.Seek(0,0);pythoncom.CoReleaseMarshalData(stream)
        raise MemoryError('Cannot allocate native interface marshal stream')
    # This pointer owns the stream reference; its destructor releases it once.
    memory_stream=ctypes.cast(address,ctypes.POINTER(comtypes.IUnknown))
    ole=ctypes.OleDLL('ole32')
    ole.CoUnmarshalInterface.argtypes=[ctypes.c_void_p,ctypes.POINTER(comtypes.GUID),ctypes.POINTER(ctypes.c_void_p)]
    pointer=ctypes.c_void_p()
    ole.CoUnmarshalInterface(address,ctypes.byref(module.IModelDocExtension._iid_),ctypes.byref(pointer))
    return ctypes.cast(pointer,ctypes.POINTER(module.IModelDocExtension))

class NativePack:
    def __init__(self,doc,major,app=None,document_adapter=lambda doc:doc):
        self.doc=doc
        self.app=app
        self.document_adapter=document_adapter
        self.extension=native_extension(doc.Extension,major)
        self.pack=self.extension.GetPackAndGo()
    def documents(self):
        paths,success=self.pack.GetDocumentNames()
        if not success:raise RuntimeError('Cannot enumerate Pack and Go source files')
        self._source_count=len(paths)
        self._sources=list(paths)
        return list(paths)
    def destinations(self,directory,prefix):
        import win32api
        target=str(directory)
        try:
            # Read an existing NTFS alias; never enable/change 8.3 or long-path
            # system settings. This keeps deep native packages below old limits.
            target=win32api.GetShortPathName(target)
        except win32api.error:
            pass
        self.pack.FlattenToSingleFolder=False
        if not self.pack.SetSaveToName(True,target):
            raise RuntimeError('Cannot assign private package directory')
        # Keep copied document titles distinct using a short prefix; the old
        # ten-character prefix pushed three real MR12 outputs over MAX_PATH.
        self.pack.AddPrefix='r-'
        self.pack.AddSuffix=''
        # Let the native package preserve subfolders and handle STEP/virtual
        # naming. On the real mixed MR12 package even identity SetDocumentSaveToNames
        # arrays were rejected; native folder assignment returned unique names.
        paths,statuses,success=self.pack.GetDocumentSaveToNames()
        if not success or any(statuses):raise RuntimeError('Cannot resolve private package destinations')
        if any(len(path)>=260 for path in paths):
            raise RuntimeError('Native package path exceeds the validated 259-character limit; choose a shorter private recovery directory')
        from .private_paths import canonical_outputs
        canonical=canonical_outputs(paths)
        root=Path(directory).resolve()
        source_count=self._source_count if hasattr(self,'_source_count') else len(self.documents())
        if (len(paths)!=source_count or len({str(p).casefold() for p in canonical})!=len(paths)
                or any(not p.is_relative_to(root) for p in canonical)):
            raise RuntimeError('Package destinations are incomplete, collide or escape the private directory')
        self._outputs=list(paths)
        return list(paths)
    def save(self):
        # Source SavePackAndGo rewrote the root assembly on disk in SW2023.
        # Use its metadata only. Never save referenced source documents.
        import shutil
        from .assembly_recovery import document_state
        from .recovery_snapshot import fingerprint,get0
        if self.app is None:raise RuntimeError('Safe package staging requires the bound application')
        statuses=[]
        root=Path(get0(self.doc,'GetPathName')).resolve()
        for source,output in zip(self._sources,self._outputs):
            destination=Path(output);destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists():raise RuntimeError('Staging destination already exists')
            raw=self.app.GetOpenDocumentByName(source)
            model=self.document_adapter(raw) if raw is not None else None
            if (Path(source).suffix.casefold() not in ('.step','.stp') and model is not None
                    and (Path(source).resolve()==root or bool(get0(model,'GetSaveFlag')))):
                before=document_state(model);sha=fingerprint(source)
                status=model.SaveAs3(str(destination),0,3) # Silent | Copy; no SaveReferenced
                if document_state(model)!=before or fingerprint(source)!=sha:
                    raise RuntimeError('Source changed during copy-only staging')
                if status:raise RuntimeError('Copy-only staging failed')
            else:
                with open(source,'rb') as src,destination.open('xb') as dst:shutil.copyfileobj(src,dst)
                shutil.copystat(source,destination)
                status=0
            statuses.append(status)
        return statuses
