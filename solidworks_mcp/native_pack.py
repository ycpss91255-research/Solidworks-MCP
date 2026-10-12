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
        if not self.pack.SetSaveToName(True,str(directory)):raise RuntimeError('Cannot assign private package directory')
        self.pack.AddPrefix=prefix
        paths,statuses,success=self.pack.GetDocumentSaveToNames()
        if not success or any(statuses):raise RuntimeError('Cannot resolve private package destinations')
        return list(paths)
    def save(self):return list(self.extension.SavePackAndGo(self.pack))
