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
    def __init__(self,doc,major):
        self.extension=native_extension(doc.Extension,major)
        self.pack=self.extension.GetPackAndGo()
    def documents(self):
        paths,success=self.pack.GetDocumentNames()
        if not success:raise RuntimeError('Cannot enumerate Pack and Go source files')
        self._source_count=len(paths)
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
        from .private_paths import canonical_outputs
        canonical=canonical_outputs(paths)
        root=Path(directory).resolve()
        source_count=self._source_count if hasattr(self,'_source_count') else len(self.documents())
        if (len(paths)!=source_count or len({str(p).casefold() for p in canonical})!=len(paths)
                or any(not p.is_relative_to(root) for p in canonical)):
            raise RuntimeError('Package destinations are incomplete, collide or escape the private directory')
        return list(paths)
    def save(self):return list(self.extension.SavePackAndGo(self.pack))
