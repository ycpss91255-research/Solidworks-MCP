import unittest
from types import SimpleNamespace
import pythoncom


class PatternInventoryTests(unittest.TestCase):
    def test_cdispatch_seed_is_bound_by_iid_not_python_class_name(self):
        from solidworks_mcp.diagnostics.pattern_inventory import bind_seed
        calls=[]
        class Raw:
            def QueryInterface(self,iid,dispatch):
                calls.append(iid)
                if iid=='component':raise pythoncom.com_error(-2147467262,'no interface',None,None)
                return 'typed-feature'
        types=SimpleNamespace(IComponent2=SimpleNamespace(CLSID='component'),IFeature=SimpleNamespace(CLSID='feature'))
        self.assertEqual(bind_seed(SimpleNamespace(_oleobj_=Raw()),types),('IFeature','typed-feature'))
        self.assertEqual(calls,['component','feature'])

    def test_native_fault_stops_instead_of_trying_another_interface(self):
        from solidworks_mcp.diagnostics.pattern_inventory import bind_seed
        calls=[]
        class Raw:
            def QueryInterface(self,iid,dispatch):
                calls.append(iid)
                raise pythoncom.com_error(-2147417851,'server fault',None,None)
        types=SimpleNamespace(IComponent2=SimpleNamespace(CLSID='component'))
        with self.assertRaises(pythoncom.com_error):bind_seed(SimpleNamespace(_oleobj_=Raw()),types)
        self.assertEqual(calls,['component'])

    def test_selection_scope_releases_when_inventory_read_fails(self):
        from solidworks_mcp.diagnostics.pattern_inventory import selection_scope
        events=[]
        definition=SimpleNamespace(AccessSelections=lambda doc,comp:events.append('access') or True,
                                   ReleaseSelectionAccess=lambda:events.append('release'))
        with self.assertRaisesRegex(ValueError,'read failed'):
            with selection_scope(definition,object()):raise ValueError('read failed')
        self.assertEqual(events,['access','release'])

    def test_selection_scope_stops_com_cleanup_after_native_server_fault(self):
        from solidworks_mcp.diagnostics.pattern_inventory import selection_scope
        events=[]
        definition=SimpleNamespace(AccessSelections=lambda doc,comp:events.append('access') or True,
                                   ReleaseSelectionAccess=lambda:events.append('release'))
        with self.assertRaises(pythoncom.com_error):
            with selection_scope(definition,object()):
                raise pythoncom.com_error(-2147417851,'server fault',None,None)
        self.assertEqual(events,['access'])
