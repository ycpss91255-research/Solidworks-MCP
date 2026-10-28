import gc
import unittest
import weakref
from unittest.mock import Mock, patch

import win32com.client
import win32com.client.dynamic

from solidworks_mcp import com_keepalive

Base = win32com.client.DispatchBaseClass
Dynamic = win32com.client.dynamic.CDispatch


def _pristine(cls):
    init = cls.__init__
    while getattr(init, '_solidworks_original', None):
        init = init._solidworks_original
    return init


def make_class(name):
    return type(name, (Base,), {'CLSID': '{00000000-0000-0000-0000-000000000000}'})


class FeatureReferenceKeeperTests(unittest.TestCase):
    def setUp(self):
        for cls in (Base, Dynamic):
            patcher = patch.object(cls, '__init__', _pristine(cls))
            patcher.start()
            self.addCleanup(patcher.stop)
        com_keepalive.release_all()
        self.addCleanup(com_keepalive.release_all)

    def _install(self, mode=None):
        env = {} if mode is None else {'SOLIDWORKS_HOLD_COM_REFS': mode}
        patcher = patch.dict('os.environ', env, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        com_keepalive.install_feature_reference_keeper()

    def test_feature_wrapper_is_held_after_the_script_drops_it(self):
        self._install()
        feature = make_class('IFeature')(Mock())
        ref = weakref.ref(feature)
        del feature
        gc.collect()
        self.assertIsNotNone(ref())
        self.assertEqual(com_keepalive.held_count(), 1)

    def test_direct_construction_from_a_raw_dispatch_is_held(self):
        # Scripts do this (m.IFeature(obj._oleobj_)); makepy methods also call Dispatch(...) which
        # ends in the same constructor, so the constructor is the only complete choke point.
        self._install()
        make_class('IFeature')(Mock())
        make_class('IFeature')(Mock())
        self.assertEqual(com_keepalive.held_count(), 2)

    def test_other_interfaces_are_not_held_by_default(self):
        self._install()
        make_class('IModelDoc2')(Mock())
        make_class('IComponent2')(Mock())
        self.assertEqual(com_keepalive.held_count(), 0)

    def test_all_mode_holds_typed_wrappers_of_any_interface(self):
        self._install('all')
        make_class('IModelDoc2')(Mock())
        make_class('IFeature')(Mock())
        self.assertEqual(com_keepalive.held_count(), 2)

    def test_all_mode_also_holds_dynamic_wrappers(self):
        self._install('all')
        Dynamic(Mock(), Mock())
        self.assertEqual(com_keepalive.held_count(), 1)

    def test_default_mode_leaves_dynamic_wrappers_alone(self):
        self._install()
        Dynamic(Mock(), Mock())
        self.assertEqual(com_keepalive.held_count(), 0)

    def test_disabled_mode_does_not_patch(self):
        before = Base.__init__
        self._install('0')
        self.assertIs(Base.__init__, before)
        make_class('IFeature')(Mock())
        self.assertEqual(com_keepalive.held_count(), 0)

    def test_install_is_idempotent(self):
        self._install()
        patched = Base.__init__
        com_keepalive.install_feature_reference_keeper()
        self.assertIs(Base.__init__, patched)
        make_class('IFeature')(Mock())
        self.assertEqual(com_keepalive.held_count(), 1)

    def test_wrapper_still_works_normally(self):
        self._install()
        oleobj = Mock()
        feature = make_class('IFeature')(oleobj)
        self.assertIs(feature._oleobj_, oleobj)

    def test_references_are_kept_while_any_document_is_open(self):
        self._install()
        make_class('IFeature')(Mock())
        app = Mock()
        app.GetDocumentCount = Mock(return_value=2)
        self.assertFalse(com_keepalive.release_if_no_documents(app))
        self.assertEqual(com_keepalive.held_count(), 1)

    def test_references_are_released_only_when_no_document_remains(self):
        self._install()
        feature = make_class('IFeature')(Mock())
        ref = weakref.ref(feature)
        del feature
        app = Mock()
        app.GetDocumentCount = Mock(return_value=0)
        self.assertTrue(com_keepalive.release_if_no_documents(app))
        gc.collect()
        self.assertEqual(com_keepalive.held_count(), 0)
        self.assertIsNone(ref())

    def test_property_style_document_count_is_supported(self):
        self._install()
        make_class('IFeature')(Mock())
        app = type('App', (), {'GetDocumentCount': 0})()
        self.assertTrue(com_keepalive.release_if_no_documents(app))

    def test_failed_document_count_keeps_references(self):
        self._install()
        make_class('IFeature')(Mock())
        app = Mock()
        app.GetDocumentCount = Mock(side_effect=RuntimeError('rpc failure'))
        self.assertFalse(com_keepalive.release_if_no_documents(app))
        self.assertEqual(com_keepalive.held_count(), 1)

    def test_no_cad_call_when_nothing_is_held(self):
        app = Mock()
        self.assertFalse(com_keepalive.release_if_no_documents(app))
        app.GetDocumentCount.assert_not_called()

    def test_missing_app_is_a_no_op(self):
        self._install()
        make_class('IFeature')(Mock())
        self.assertFalse(com_keepalive.release_if_no_documents(None))
        self.assertEqual(com_keepalive.held_count(), 1)


class AutomationReleaseHookTests(unittest.TestCase):
    def _automation(self, blocked=None):
        from solidworks_mcp.automation.base import SolidWorksAutomation
        automation = SolidWorksAutomation.__new__(SolidWorksAutomation)
        automation._sw_app = object()
        automation.native_fault_result = Mock(return_value=blocked)
        return automation

    def test_idle_release_uses_the_bound_application(self):
        automation = self._automation()
        with patch('solidworks_mcp.com_keepalive.release_if_no_documents', return_value=True) as release:
            self.assertTrue(automation.release_idle_com_references())
        release.assert_called_once_with(automation._sw_app)

    def test_no_cad_query_while_a_native_fault_is_quarantined(self):
        automation = self._automation(blocked={'success': False})
        with patch('solidworks_mcp.com_keepalive.release_if_no_documents') as release:
            self.assertFalse(automation.release_idle_com_references())
        release.assert_not_called()


if __name__ == '__main__':
    unittest.main()
