"""Regression gates derived from real false-green and rebuild-failure evidence."""
import copy
import unittest

from solidworks_mcp.diagnostics.configuration_acceptance import assert_geometry


class ConfigurationAcceptanceTests(unittest.TestCase):
    def test_hole_faces_use_part_interface_and_reject_missing_feature(self):
        from types import SimpleNamespace
        from solidworks_mcp.diagnostics.configuration_acceptance import _feature_faces
        feature = SimpleNamespace(_oleobj_='hole')
        part = SimpleNamespace(FeatureByName=lambda name: feature if name == '端孔' else None)
        types = SimpleNamespace(IFeature=lambda raw: SimpleNamespace(GetFaces=lambda: ['face']))
        self.assertEqual(_feature_faces(types, part, '端孔'), ['face'])
        with self.assertRaisesRegex(AssertionError, 'missing'):
            _feature_faces(types, part, 'missing')

    def setUp(self):
        self.expected = dict(configuration='斜撐', length_mm=1332.097557,
                             hole_span_mm=1312.097557, equation_count=18)
        self.observation = dict(configuration='斜撐', rebuild=True,
            length_mm=1332.097557, hole_span_mm=1312.097557,
            equation_count=18, equation_errors=[], feature_errors=[], solid_body_count=1)

    def test_valid_rebuilt_physical_geometry_passes(self):
        assert_geometry(self.observation, self.expected)

    def test_real_error51_case_cannot_pass_on_correct_dimensions(self):
        row = copy.deepcopy(self.observation)
        row.update(rebuild=False, feature_errors=[{'feature': '轉換成實體', 'code': 51}])
        with self.assertRaisesRegex(AssertionError, 'rebuild|feature'):
            assert_geometry(row, self.expected)

    def test_no_solid_body_cannot_pass_on_dimensions_alone(self):
        row = self.observation | {'solid_body_count': 0}
        with self.assertRaisesRegex(AssertionError, 'solid'):
            assert_geometry(row, self.expected)

    def test_cached_dimension_cannot_replace_actual_hole_geometry(self):
        row = self.observation | {'hole_span_mm': 1040.0}
        with self.assertRaisesRegex(AssertionError, 'hole_span'):
            assert_geometry(row, self.expected)

    def test_wrong_configuration_and_equation_failure_are_rejected(self):
        for patch in ({'configuration':'橫撐'}, {'equation_errors':[{'index':4,'status':-1}]},
                      {'equation_count':29}):
            with self.subTest(patch=patch), self.assertRaises(AssertionError):
                assert_geometry(self.observation | patch, self.expected)

    def test_missing_and_nonfinite_measurements_cannot_pass(self):
        for value in (None, float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(AssertionError):
                assert_geometry(self.observation | {'hole_span_mm':value}, self.expected)
        with self.assertRaises(AssertionError):
            assert_geometry({}, self.expected)
