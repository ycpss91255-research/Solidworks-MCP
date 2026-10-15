"""Observe identity-bound native failures consumed inside a custom Python request."""
import sys
import threading
from .native_fault import native_hresult

class NativeFaultObservation:
    def __init__(self, automation, *, monitoring=True):
        self.automation = automation
        self.monitoring = getattr(sys, 'monitoring', None) if monitoring else None
        self.tool_id = None
        self.error = None
        self.thread_id = threading.get_ident()
        self.previous = None
        self.caller = None
        self.trace_active = False

    def observe(self, error):
        if (self.error is None and threading.get_ident() == self.thread_id
                and native_hresult(error) is not None):
            self.error = error
            self.automation.record_native_failure(error)

    def raised(self, code, offset, error):
        self.observe(error)

    def trace(self, frame, event, argument):
        delegate = self.previous(frame, event, argument) if self.previous else None
        if delegate is None:
            frame.f_trace_lines = False
        return self.local_trace(delegate)

    def local_trace(self, delegate):
        def local(current, kind, value):
            nonlocal delegate
            if kind == 'exception':
                self.observe(value[1])
            if delegate is not None:
                delegate = delegate(current, kind, value)
            return local
        return local

    def __enter__(self):
        if self.monitoring is not None:
            for candidate in (3, 4):
                try:
                    self.monitoring.use_tool_id(candidate, 'solidworks-native-fault')
                except ValueError:
                    continue
                self.tool_id = candidate
                break
        if self.tool_id is not None:
            try:
                self.monitoring.register_callback(self.tool_id, self.monitoring.events.RAISE, self.raised)
                self.monitoring.set_events(self.tool_id, self.monitoring.events.RAISE)
            except BaseException:
                self.cleanup()
                raise
        else:
            self.previous = sys.gettrace()
            self.caller = sys._getframe(1)
            self.caller_previous = self.caller.f_trace
            self.caller_lines = self.caller.f_trace_lines
            self.caller.f_trace = self.local_trace(self.caller_previous)
            if self.caller_previous is None:
                self.caller.f_trace_lines = False
            sys.settrace(self.trace)
            self.trace_active = True
        return self

    def cleanup(self):
        if self.tool_id is not None:
            tool_id, self.tool_id = self.tool_id, None
            self.monitoring.set_events(tool_id, 0)
            self.monitoring.register_callback(tool_id, self.monitoring.events.RAISE, None)
            self.monitoring.free_tool_id(tool_id)
        elif self.trace_active:
            sys.settrace(self.previous)
            self.caller.f_trace = self.caller_previous
            self.caller.f_trace_lines = self.caller_lines
            self.caller = None
            self.trace_active = False

    def __exit__(self, kind, error, traceback):
        self.cleanup()
        observed, self.error = self.error, None
        if observed is not None and kind is None:
            raise observed
        return False
