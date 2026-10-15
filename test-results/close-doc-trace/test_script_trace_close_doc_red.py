"""No-CAD regression for exact generated CloseDoc call breadcrumbs."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

import pythoncom
from solidworks_mcp.script_trace import ScriptTrace


MODULE = 'win32com.gen_py.83A33D31-27C5-11CE-BFD4-00400513BB57x0x31x0'
GENERATED_FILE = 'C:/fake-pywin32-cache/gen_py/solidworks.py'
WRAPPER = '''class ISldWorks:
    CLSID = IID('{83A33D22-27C5-11CE-BFD4-00400513BB57}')
    def CloseDoc(self, Name):
        return self._oleobj_.InvokeTypes(7, 0, 1, (24, 0), ((8, 1),), Name)
    def Other(self, Name):
        return self._oleobj_.InvokeTypes(8, 0, 1, (24, 0), ((8, 1),), Name)
'''


class FakeOle:
    def __init__(self, failing_title=None):
        self.failing_title = failing_title
        self.calls = []

    def InvokeTypes(self, *args):
        title = args[-1]
        self.calls.append(title)
        if type(title) is str and title == self.failing_title:
            raise RuntimeError('simulated failure; no CAD')
        return None


@contextmanager
def generated_wrapper(module_name=MODULE):
    module = types.ModuleType(module_name)
    module.__file__ = GENERATED_FILE
    module.IID = pythoncom.MakeIID
    exec(compile(WRAPPER, GENERATED_FILE, 'exec'), module.__dict__)
    with patch.dict(sys.modules, {module_name: module}):
        yield module


class CloseDocTraceTests(unittest.TestCase):
    def run_script(self, code, namespace, expected_error=None):
        with tempfile.TemporaryDirectory() as directory, \
                patch('solidworks_mcp.script_trace.memory_snapshot', return_value={}):
            previous = sys.gettrace()
            if expected_error:
                with self.assertRaises(expected_error):
                    with ScriptTrace(code, 4321, directory) as trace:
                        exec(trace.compiled, namespace)
            else:
                with ScriptTrace(code, 4321, directory) as trace:
                    exec(trace.compiled, namespace)
            self.assertIs(sys.gettrace(), previous)
            rows = [json.loads(line) for line in
                    (Path(directory)/(trace.name+'.jsonl')).read_text().splitlines()]
            return [row for row in rows if row['event'].startswith('close_doc_')], trace.filename

    def test_loop_records_exact_titles_and_callsite(self):
        with generated_wrapper() as module:
            sw = module.ISldWorks(); sw._oleobj_ = FakeOle()
            rows, filename = self.run_script('for title in titles:\n sw.CloseDoc(title)',
                                            {'sw': sw, 'titles': ['first.SLDASM', '第二份.SLDPRT']})
        self.assertEqual([(r['event'], r['title']) for r in rows],
                         [('close_doc_begin', 'first.SLDASM'), ('close_doc_end', 'first.SLDASM'),
                          ('close_doc_begin', '第二份.SLDPRT'), ('close_doc_end', '第二份.SLDPRT')])
        self.assertEqual(sw._oleobj_.calls, ['first.SLDASM', '第二份.SLDPRT'])
        for row in rows:
            self.assertEqual(row['api'], 'ISldWorks.CloseDoc')
            self.assertEqual((row['caller_filename'], row['caller_line']), (filename, 2))
            self.assertEqual(row['solidworks_pid'], 4321)
            self.assertIs(type(row['time_ns']), int)
            self.assertIs(type(row['server_pid']), int)

    def test_failure_names_exact_iteration_without_false_end(self):
        with generated_wrapper() as module:
            sw = module.ISldWorks(); sw._oleobj_ = FakeOle('bad.SLDASM')
            rows, _ = self.run_script('for title in titles:\n sw.CloseDoc(title)',
                                     {'sw': sw, 'titles': ['ok.SLDASM', 'bad.SLDASM', 'never.SLDASM']},
                                     RuntimeError)
        self.assertEqual([(r['event'], r['title']) for r in rows],
                         [('close_doc_begin', 'ok.SLDASM'), ('close_doc_end', 'ok.SLDASM'),
                          ('close_doc_begin', 'bad.SLDASM'), ('close_doc_fail', 'bad.SLDASM')])
        self.assertEqual(sw._oleobj_.calls, ['ok.SLDASM', 'bad.SLDASM'])

    def test_non_close_and_same_named_fake_objects_are_excluded(self):
        with generated_wrapper() as module, generated_wrapper('ordinary_user_module') as fake_module:
            sw = module.ISldWorks(); sw._oleobj_ = FakeOle()
            fake = fake_module.ISldWorks(); fake._oleobj_ = FakeOle()
            impostor = type('Impostor', (), {'CloseDoc': module.ISldWorks.CloseDoc})()
            impostor._oleobj_ = FakeOle()
            rows, _ = self.run_script("sw.Other('other')\nfake.CloseDoc('fake')\nimpostor.CloseDoc('borrowed')",
                                     {'sw': sw, 'fake': fake, 'impostor': impostor})
        self.assertEqual(rows, [])
        self.assertEqual(fake._oleobj_.calls, ['fake'])
        self.assertEqual(impostor._oleobj_.calls, ['borrowed'])

    def test_non_plain_string_is_not_inspected_or_coerced(self):
        class Hostile:
            def __repr__(self): raise AssertionError('Do not repr user objects')
            def __str__(self): raise AssertionError('Do not stringify user objects')
        class HostileString(str):
            def __str__(self): raise AssertionError('Do not coerce string subclasses')
        with generated_wrapper() as module:
            sw = module.ISldWorks(); sw._oleobj_ = FakeOle()
            rows, _ = self.run_script('sw.CloseDoc(value)\nsw.CloseDoc(subclass)',
                                     {'sw': sw, 'value': Hostile(), 'subclass': HostileString('x')})
        self.assertEqual(rows, [])
        self.assertEqual(len(sw._oleobj_.calls), 2)

    def test_trace_is_scoped_to_current_thread(self):
        with generated_wrapper() as module:
            sw = module.ISldWorks(); sw._oleobj_ = FakeOle()
            rows, _ = self.run_script(
                "child=threading.Thread(target=sw.CloseDoc,args=('other-thread',))\n"
                "child.start()\nchild.join()\nsw.CloseDoc('owner-thread')",
                {'sw': sw, 'threading': threading})
        self.assertEqual([r['title'] for r in rows], ['owner-thread', 'owner-thread'])
        self.assertEqual(sw._oleobj_.calls, ['other-thread', 'owner-thread'])


if __name__ == '__main__':
    unittest.main()
