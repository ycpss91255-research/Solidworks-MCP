"""Offline actual generated wrapper + fake InvokeTypes; no CAD connection."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from solidworks_mcp.script_trace import ScriptTrace

source = Path('C:/Users/YUNCHI~1.CHE/AppData/Local/Temp/gen_py/3.14/83A33D31-27C5-11CE-BFD4-00400513BB57x0x31x0.py')
name = 'win32com.gen_py.83A33D31-27C5-11CE-BFD4-00400513BB57x0x31x0'
spec = importlib.util.spec_from_file_location(name, source)
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)

class FakeOle:
    def __init__(self): self.calls = []
    def InvokeTypes(self, *args):
        assert args[:5] == (7, 0, 1, (24, 0), ((8, 1),))
        self.calls.append(args[-1])
        if args[-1] == 'bad.SLDASM': raise RuntimeError('Fake exception; no native invocation')

# Explicitly bypass DispatchBaseClass construction and its possible QI.
sw = object.__new__(module.ISldWorks)
backend = FakeOle()
sw.__dict__['_oleobj_'] = backend
with tempfile.TemporaryDirectory() as directory, patch('solidworks_mcp.script_trace.memory_snapshot', return_value={}):
    try:
        with ScriptTrace('for title in titles:\n sw.CloseDoc(title)', 4321, directory) as trace:
            exec(trace.compiled, {'sw': sw, 'titles': ['ok.SLDASM', 'bad.SLDASM', 'never.SLDASM']})
    except RuntimeError as error:
        assert str(error) == 'Fake exception; no native invocation'
    else:
        raise AssertionError('Expected fake backend failure')
    rows = [json.loads(line) for line in (Path(directory)/(trace.name+'.jsonl')).read_text().splitlines()]
    breadcrumbs = [row for row in rows if row['event'].startswith('close_doc_')]
assert [(row['event'], row['title']) for row in breadcrumbs] == [
    ('close_doc_begin', 'ok.SLDASM'), ('close_doc_end', 'ok.SLDASM'),
    ('close_doc_begin', 'bad.SLDASM'), ('close_doc_fail', 'bad.SLDASM')]
assert backend.calls == ['ok.SLDASM', 'bad.SLDASM']
proof = {'passed': True, 'actual_cad_calls': 0, 'com_connections': 0,
         'generated_source': str(source), 'generated_source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
         'wrapper_module': name, 'wrapper_class': type(sw).__name__, 'fake_backend_calls': backend.calls,
         'breadcrumbs': breadcrumbs, 'source_sha256': hashlib.sha256((ROOT/'solidworks_mcp/script_trace.py').read_bytes()).hexdigest()}
out = Path(__file__).with_name('actual-generated-wrapper.json')
out.write_text(json.dumps(proof, indent=2)+'\n', encoding='utf8')
print(json.dumps({'passed': True, 'path': str(out), 'actual_cad_calls': 0}))
