"""Explicit-IID seed binding and balanced pattern-selection diagnostics.

Selection access rolls a feature back. Releasing it may regenerate components;
these helpers are opt-in diagnostics, not a passive crash-prevention hook.
The caller must verify its owned PID and private document paths first. No
connection, startup, save, feature-property change or close is implicit here.
"""
from contextlib import contextmanager


def bind_seed(raw, types):
    import pythoncom
    try:
        bound=raw._oleobj_.QueryInterface(types.IComponent2.CLSID,pythoncom.IID_IDispatch)
        return 'IComponent2',bound
    except pythoncom.com_error as error:
        if error.hresult != -2147467262:raise  # E_NOINTERFACE only
    bound=raw._oleobj_.QueryInterface(types.IFeature.CLSID,pythoncom.IID_IDispatch)
    return 'IFeature',bound


@contextmanager
def selection_scope(definition, doc):
    import pythoncom
    assert definition.AccessSelections(doc,None), 'pattern selection access failed'
    fatal=False
    try:
        yield definition
    except pythoncom.com_error as error:
        fatal=error.hresult in (-2147417851,-2147417848,-2147023174,-2147023170,-2147023169)
        raise
    finally:
        if not fatal:definition.ReleaseSelectionAccess()
