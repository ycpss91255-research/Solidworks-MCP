"""Guard the typed COM dependency query that reproduced a native CAD fault."""
from functools import wraps
import win32com.client

MODEL_EXTENSION_IID = '{99F4D4AF-F268-4EE1-8C55-041F7BECF879}'


def install_dependency_query_guard():
    original = win32com.client.DispatchBaseClass._ApplyTypes_
    if getattr(original, '_solidworks_dependency_guard', False):
        return

    @wraps(original)
    def guarded(self, dispid, flags, return_type, argument_types, user, result_clsid, *arguments):
        # Read only the Python class identity; never query CAD to decide safety.
        identity = str(getattr(type(self), 'CLSID', '')).upper()
        if identity == MODEL_EXTENSION_IID and dispid == 306 and flags & 1:
            raise RuntimeError(
                'IModelDocExtension.GetDependencies is disabled in this MCP: it '
                'reproduced a native sldapiu.dll access violation in the installed '
                'SolidWorks. Use the existing PackAndGo metadata recovery path; '
                'GetDocumentDependencies2/GetDependencies2 provide narrower inventories. '
                'No replacement API was called automatically.')
        return original(self, dispid, flags, return_type, argument_types,
                        user, result_clsid, *arguments)

    guarded._solidworks_dependency_guard = True
    win32com.client.DispatchBaseClass._ApplyTypes_ = guarded
