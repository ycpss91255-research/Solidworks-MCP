"""Keep IFeature wrappers alive until no document is open.

Evidence (2026-10-27 MR12 investigation, docs/solidworks-root-cause-findings-2026-10-27.md):
SolidWorks 2023 SP5.0 keeps an unowned pointer to the API wrapper object (slduiu!auFeature_c) inside
the internal feature. When the client releases its last IFeature reference the wrapper is destroyed
but the internal pointer is not cleared; the freed block is reused, and closing the document later
dereferences the stale pointer. Holding every IFeature reference until the document is closed removed
the CloseDoc fault in a controlled comparison (5/8 vs 0/8 in the typed C# harness).

pywin32 releases a wrapper as soon as its Python object dies, which happens at the end of every
execute_python script. This module holds IFeature wrappers instead and drops them only when the
application reports no open document. It never calls CAD except one read-only GetDocumentCount, and
only when something is held.

The hook is DispatchBaseClass.__init__: makepy-generated methods wrap results with
``Dispatch(ret, ...)`` bound at import time, and scripts also construct typed wrappers directly
(``m.IFeature(obj._oleobj_)``), so only the constructor sees every typed wrapper.

SOLIDWORKS_HOLD_COM_REFS: unset/'feature' hold IFeature (default); 'all' hold every COM wrapper
including dynamic ones; '0'/'off'/'false' do nothing.
"""
import logging
import os
import threading

import win32com.client
import win32com.client.dynamic

logger = logging.getLogger(__name__)

HOLD_CLASS_NAMES = frozenset({'IFeature'})
WARN_HELD_COUNT = 50000

_lock = threading.Lock()
_held = []
_warned = False


def _mode():
    value = os.environ.get('SOLIDWORKS_HOLD_COM_REFS', 'feature').strip().lower()
    if value in ('0', 'off', 'false', 'no'):
        return 'off'
    return 'all' if value == 'all' else 'feature'


def _should_hold(wrapper, mode):
    if mode == 'off' or '_oleobj_' not in getattr(wrapper, '__dict__', {}):
        return False
    return mode == 'all' or type(wrapper).__name__ in HOLD_CLASS_NAMES


def _hold(wrapper):
    global _warned
    with _lock:
        _held.append(wrapper)
        if len(_held) >= WARN_HELD_COUNT and not _warned:
            _warned = True
            logger.warning('%d COM wrappers are held until all documents close', len(_held))


def _patch_init(cls):
    original = cls.__init__
    if getattr(original, '_solidworks_feature_keeper', False):
        return

    def keeping_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        if _should_hold(self, _mode()):
            _hold(self)

    keeping_init._solidworks_feature_keeper = True
    keeping_init._solidworks_original = original
    cls.__init__ = keeping_init


def install_feature_reference_keeper():
    mode = _mode()
    if mode == 'off':
        return
    _patch_init(win32com.client.DispatchBaseClass)
    logger.info('IFeature reference keeper installed (mode=%s)', mode)
    if mode == 'all':
        _patch_init(win32com.client.dynamic.CDispatch)


def held_count():
    with _lock:
        return len(_held)


def release_all():
    with _lock:
        items = list(_held)
        _held.clear()
    count = len(items)
    del items
    return count


def release_if_no_documents(app):
    """Drop held wrappers once the application reports zero open documents."""
    if app is None or held_count() == 0:
        return False
    try:
        count = app.GetDocumentCount
        if callable(count):
            count = count()
        if int(count) != 0:
            return False
    except Exception:
        logger.debug('GetDocumentCount failed; wrappers stay held', exc_info=True)
        return False
    released = release_all()
    logger.info('Released %d held COM wrappers; no documents are open', released)
    return True
