import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from solidworks_mcp.automation.mates import MateOperations


class Harness(MateOperations):
    _connected = True
    _target_pid = '123'

    def _result(self, success, message, error_code=0, data=None):
        return dict(success=success, message=message, data=data)


class MateReplacementTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.h._sw_app = Mock()
        self.h._sw_app.GetProcessID.return_value = 123
        self.args = dict(filepath='C:/private/test.SLDASM', mate_name='travel',
                         minimum_m=.01, maximum_m=1., distance_m=.1,
                         allow_identity_change=True)

    def test_invalid_request_never_touches_com(self):
        for override in ({'allow_identity_change': False}, {'minimum_m': float('nan')},
                         {'distance_m': 2.}, {'maximum_m': True}, {'filepath': 'relative'}):
            with self.subTest(override=override):
                result = self.h.recreate_distance_mate_as_limit(**(self.args | override))
                self.assertFalse(result['success'])
                self.assertFalse(result['data']['partial_change'])
        self.h._sw_app.GetProcessID.assert_not_called()

    def test_wrong_pid_never_loads_or_modifies_document(self):
        self.h._sw_app.GetProcessID.return_value = 999
        result = self.h.recreate_distance_mate_as_limit(**self.args)
        self.assertFalse(result['success'])
        self.h._sw_app.GetOpenDocumentByName.assert_not_called()

    def fixture(self, select_ok=True, create_ok=True):
        app = self.h._sw_app
        app._oleobj_ = app
        app.RevisionNumber.return_value = '31.5.0.52'
        app.ActivateDoc3.return_value = (True, 0)
        doc = Mock()
        doc.GetType.return_value = 2
        doc.GetPathName.return_value = self.args['filepath']
        doc._oleobj_ = doc
        app.GetOpenDocumentByName.return_value = doc
        old = Mock()
        old._oleobj_ = old
        old.GetTypeName2.return_value = 'MateDistanceDim'
        definition = SimpleNamespace(IsAdvancedMate=False, FlipDimension=False)
        definition._oleobj_ = definition
        old.GetDefinition.return_value = definition
        mate = Mock()
        mate._oleobj_ = mate
        mate.GetMateEntityCount.return_value = 2
        ref = Mock()
        ref.Select4.return_value = select_ok
        entity = SimpleNamespace(Reference=ref)
        entity._oleobj_ = entity
        mate.MateEntity.return_value = entity
        old.GetSpecificFeature2.return_value = mate
        manager = Mock()
        manager._oleobj_ = manager
        manager.GetSelectedObjectCount2.return_value = 2
        sd = SimpleNamespace()
        sd._oleobj_ = sd
        manager.CreateSelectData.return_value = sd
        doc.SelectionManager = manager
        doc.AddMate5.return_value = (True, 1) if create_ok else (None, 0)
        new = Mock()
        new.GetTypeName2.return_value = 'MateLimitDistanceDim'
        fresh = SimpleNamespace(IsAdvancedMate=True, MinimumDistance=.01,
                                MaximumDistance=1., Distance=.1)
        fresh._oleobj_ = fresh
        new.GetDefinition.return_value = fresh
        new.GetErrorCode2.return_value = (0, 0)
        types = SimpleNamespace(**{name: lambda x: x for name in
            ['ISldWorks', 'IModelDoc2', 'IDistanceMateFeatureData', 'IMate2', 'IMateEntity2',
             'ISelectionMgr', 'ISelectData', 'IAssemblyDoc']})
        return doc, old, new, types

    def run_fixture(self, select_ok=True, create_ok=True):
        doc, old, new, types = self.fixture(select_ok, create_ok)
        with patch('solidworks_mcp.automation.mates.gencache.EnsureModule', return_value=types), \
             patch('solidworks_mcp.automation.mates._features', side_effect=[
                 {'travel': [old]}, {}, {'new': [new]}]):
            result = self.h.recreate_distance_mate_as_limit(**self.args)
        return result, doc, old

    def test_failed_preselection_does_not_delete_original(self):
        result, doc, old = self.run_fixture(select_ok=False)
        self.assertFalse(result['success'])
        doc.Extension.DeleteSelection2.assert_not_called()
        doc.AddMate5.assert_not_called()
        self.assertFalse(result['data']['partial_change'])

    def test_failure_after_delete_is_explicit_and_not_saved_or_retried(self):
        result, doc, old = self.run_fixture(create_ok=False)
        self.assertFalse(result['success'])
        self.assertTrue(result['data']['partial_change'])
        doc.AddMate5.assert_called_once()
        doc.Save3.assert_not_called()

    def test_success_creates_new_definition_without_converting_original(self):
        result, doc, old = self.run_fixture()
        self.assertTrue(result['success'], result)
        self.assertTrue(result['data']['feature_identity_changed'])
        old.ModifyDefinition.assert_not_called()
        doc.Save3.assert_not_called()
        self.h._sw_app.CloseDoc.assert_not_called()

    def test_dynamic_pid_and_revision_properties_are_supported(self):
        doc, old, new, types = self.fixture()
        self.h._sw_app.GetProcessID = 123
        self.h._sw_app.RevisionNumber = '31.5.0.52'
        with patch('solidworks_mcp.automation.mates.gencache.EnsureModule', return_value=types), \
             patch('solidworks_mcp.automation.mates._features', side_effect=[
                 {'travel': [old]}, {}, {'new': [new]}]):
            result = self.h.recreate_distance_mate_as_limit(**self.args)
        self.assertTrue(result['success'], result)
