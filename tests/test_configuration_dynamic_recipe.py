import unittest
from pathlib import Path
from types import SimpleNamespace


class DynamicRecipeIsolationTests(unittest.TestCase):
    def test_wrong_pid_stops_before_document_access(self):
        from tests.configuration_dynamic_recipe import restore_binding
        sw=SimpleNamespace(GetProcessID=lambda: 100)
        with self.assertRaisesRegex(AssertionError,'PID'):
            restore_binding(sw, None, str(Path.cwd()), 101)

    def test_other_document_stops_before_mutation(self):
        from tests.configuration_dynamic_recipe import restore_binding
        sw=SimpleNamespace(GetProcessID=lambda:100,GetDocuments=lambda:[SimpleNamespace(_oleobj_='other')])
        types=SimpleNamespace(IModelDoc2=lambda raw:SimpleNamespace(GetPathName=lambda:str(Path.cwd().parent/'other.SLDPRT')))
        with self.assertRaisesRegex(AssertionError,'private'):
            restore_binding(sw,types,str(Path.cwd()),100)
