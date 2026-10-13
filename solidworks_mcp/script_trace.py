"""Opt-in, thread-scoped breadcrumbs for diagnosing native CAD exits."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import time
import uuid


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

    def record(self, event, frame=None):
        value = {'time_ns': time.time_ns(), 'server_pid': os.getpid(),
                 'solidworks_pid': self.pid, 'event': event,
                 'memory': memory_snapshot()}
        if frame is not None:
            value.update(filename=frame.f_code.co_filename, line=frame.f_lineno)
        self.stream.write(json.dumps(value) + '\n')
        self.stream.flush()  # Survives abrupt interpreter/native server failure.

    def trace(self, frame, event, _):
        filename = frame.f_code.co_filename
        selected = filename == self.filename or filename == '<string>'
        if not selected and not filename.startswith('<'):
            path = Path(filename).resolve()
            selected = path.is_relative_to(self.script_root) and not any(
                part in ('.venv', 'site-packages', 'solidworks_mcp') for part in path.parts)
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
            self.stream.close()
