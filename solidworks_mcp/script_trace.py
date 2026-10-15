"""Opt-in, thread-scoped breadcrumbs for diagnosing native CAD exits."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time
import uuid
import types
from pywintypes import IID


_ISLDWORKS_IID = IID('{83A33D22-27C5-11CE-BFD4-00400513BB57}')


def memory_snapshot():
    class Performance(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in
            ('CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal',
             'PhysicalAvailable', 'SystemCache', 'KernelTotal', 'KernelPaged',
             'KernelNonpaged', 'PageSize')] + [(name, wintypes.DWORD) for name in
             ('HandleCount', 'ProcessCount', 'ThreadCount')]
    value = Performance()
    value.cb = ctypes.sizeof(value)
    api = ctypes.WinDLL('psapi', use_last_error=True).GetPerformanceInfo
    api.argtypes = [ctypes.POINTER(Performance), wintypes.DWORD]
    api.restype = wintypes.BOOL
    if not api(ctypes.byref(value), value.cb):
        return {'error': ctypes.get_last_error()}
    return {'commit_bytes': value.CommitTotal * value.PageSize,
            'commit_limit_bytes': value.CommitLimit * value.PageSize,
            'available_physical_bytes': value.PhysicalAvailable * value.PageSize}


class ScriptTrace:
    def __init__(self, code, pid, directory):
        self.code = code
        self.pid = pid
        self.directory = Path(directory)
        if not self.directory.is_absolute():
            raise ValueError('SOLIDWORKS_SCRIPT_TRACE_DIR must be absolute')
        self.name = f'script-{os.getpid()}-{uuid.uuid4().hex}'
        self.filename = f'<{self.name}>'
        self.compiled = compile(code, self.filename, 'exec')
        self.previous = None
        self.stream = None
        self.script_root = Path.cwd().resolve()
        self.dynamic_code = {}
        self.file_selection = {}
        # Store only scalar call metadata, never frames or COM wrappers.
        self.close_doc_calls = {}
        self.close_doc_breadcrumb_errors = 0

    def _script_file(self, filename):
        if filename.startswith('<'):
            return False
        if filename in self.file_selection:
            return self.file_selection[filename]
        path = Path(filename).resolve()
        selected = path.is_relative_to(self.script_root) and not any(
            part in ('.venv', 'site-packages', 'solidworks_mcp') for part in path.parts)
        self.file_selection[filename] = selected
        return selected

    def _accept_dynamic(self, code):
        self.dynamic_code[id(code)] = code
        for child in code.co_consts:
            if isinstance(child, types.CodeType):
                self._accept_dynamic(child)

    def record(self, event, frame=None, **details):
        value = {'time_ns': time.time_ns(), 'server_pid': os.getpid(),
                 'solidworks_pid': self.pid, 'event': event,
                 'memory': memory_snapshot()}
        if frame is not None:
            value.update(filename=frame.f_code.co_filename, line=frame.f_lineno)
        value.update(details)
        if self.close_doc_breadcrumb_errors:
            value['close_doc_breadcrumb_errors'] = self.close_doc_breadcrumb_errors
        self.stream.write(json.dumps(value) + '\n')
        self.stream.flush()  # Survives abrupt interpreter/native server failure.

    def _close_doc_metadata(self, frame):
        """Recognize the loaded generated wrapper without inspecting COM state."""
        if frame.f_code.co_name != 'CloseDoc':
            return None
        namespace = frame.f_globals
        module_name = namespace.get('__name__')
        if type(module_name) is not str or not module_name.startswith('win32com.gen_py.'):
            return None
        module = sys.modules.get(module_name)
        if type(module) is not types.ModuleType or vars(module) is not namespace:
            return None
        cls = namespace.get('ISldWorks')
        if type(cls) is not type or type(frame.f_locals.get('self')) is not cls:
            return None
        members = type.__getattribute__(cls, '__dict__')
        iid = members.get('CLSID')
        method = members.get('CloseDoc')
        if (type(iid) is not type(_ISLDWORKS_IID) or iid != _ISLDWORKS_IID
                or type(method) is not types.FunctionType
                or method.__code__ is not frame.f_code
                or method.__globals__ is not namespace):
            return None
        title = frame.f_locals.get('Name')
        if type(title) is not str:
            return None  # Do not coerce, repr, or read attributes of caller values.
        caller = frame.f_back
        return {'api': 'ISldWorks.CloseDoc', 'title': title,
                'caller_filename': caller.f_code.co_filename if caller else None,
                'caller_line': caller.f_lineno if caller else None}

    def _record_close_doc(self, event, frame, details):
        try:
            self.record(event, frame, **details)
        except Exception:
            # This additional diagnostic must not prevent a call, replace its
            # original exception, or turn a successful return into a failure.
            self.close_doc_breadcrumb_errors += 1

    def trace(self, frame, event, _):
        key = id(frame)
        if event == 'call':
            details = self._close_doc_metadata(frame)
            if details is not None:
                self.close_doc_calls[key] = (details, False)
                self._record_close_doc('close_doc_begin', frame, details)
                return self.trace
        elif key in self.close_doc_calls:
            details, failed = self.close_doc_calls[key]
            if event == 'exception' and not failed:
                self._record_close_doc('close_doc_fail', frame, details)
                self.close_doc_calls[key] = (details, True)
            elif event == 'return':
                if not failed:
                    self._record_close_doc('close_doc_end', frame, details)
                del self.close_doc_calls[key]
            return self.trace
        filename = frame.f_code.co_filename
        selected = filename == self.filename or id(frame.f_code) in self.dynamic_code
        if filename == '<string>' and event == 'call' and frame.f_code.co_name == '<module>':
            parent = frame.f_back
            if parent and (parent.f_code.co_filename == self.filename or
                           id(parent.f_code) in self.dynamic_code or
                           self._script_file(parent.f_code.co_filename)):
                self._accept_dynamic(frame.f_code)
                selected = True
        if not selected:
            selected = self._script_file(filename)
        if not selected:
            return None
        if event in ('line', 'return', 'exception'):
            self.record(event, frame)
        return self.trace

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / (self.name + '.py')).write_text(self.code, encoding='utf-8')
        self.stream = (self.directory / (self.name + '.jsonl')).open('w', encoding='utf-8')
        self.previous = sys.gettrace()
        self.record('start')
        sys.settrace(self.trace)
        return self

    def __exit__(self, kind, *_):
        sys.settrace(self.previous)
        try:
            self.record('failed' if kind else 'completed')
        finally:
            self.close_doc_calls.clear()
            self.stream.close()
