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
        return list(paths)
    def destinations(self,directory,prefix):
        import hashlib
        from comtypes import BSTR
        from comtypes.automation import VARIANT
        from comtypes.safearray import _midlSAFEARRAY
        sources=self.documents()
        counts={}
        for source in sources:
            name=Path(source).name.casefold();counts[name]=counts.get(name,0)+1
        outputs=[]
        for source in sources:
            name=Path(source).name
            unique=hashlib.sha256(str(Path(source).resolve()).casefold().encode()).hexdigest()[:12]+'-' if counts[name.casefold()]>1 else ''
            outputs.append(str(Path(directory)/(prefix+unique+name)))
        # Global folder override flattens duplicate basenames. Assign each
        # document explicitly and let Pack and Go rewrite its references.
        self.pack.SetSaveToName(False,'')
        self.pack.AddPrefix=''
        self.pack.AddSuffix=''
        names=VARIANT(_midlSAFEARRAY(BSTR).create(outputs))
        if not self.pack.SetDocumentSaveToNames(names):
            raise RuntimeError('Cannot assign private per-document package names')
        paths,statuses,success=self.pack.GetDocumentSaveToNames()
        if not success or any(statuses):raise RuntimeError('Cannot resolve private package destinations')
        if len(paths)!=len(outputs) or any(str(Path(a).resolve()).casefold()!=str(Path(b).resolve()).casefold() for a,b in zip(paths,outputs)):
            raise RuntimeError('Pack and Go did not retain the requested private destinations')
        return list(paths)
    def save(self):return list(self.extension.SavePackAndGo(self.pack))
