import copy
import unittest


class AssemblyAcceptanceTests(unittest.TestCase):
    def test_physical_grid_rejects_correct_count_at_wrong_spacing(self):
        from solidworks_mcp.diagnostics.configuration_assembly_acceptance import assert_brace_grid
        pairs=[[(0.,i*.8,0.),(0.,(i+1)*.8,1.04)] for i in range(4)]
        assert_brace_grid(pairs,4,3.2,1.04)
        broken=copy.deepcopy(pairs);broken[2][1]=(0.,2.5,1.04)
        with self.assertRaises(AssertionError):assert_brace_grid(broken,4,3.2,1.04)

    def setUp(self):
        self.rows=[dict(name='brace-1',configuration='斜撐',suppressed=False,
            source_path='C:/private/brace.SLDPRT',matrix=[1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.])]

    def test_roundtrip_numeric_identity_and_expected_count(self):
        from solidworks_mcp.diagnostics.configuration_assembly_acceptance import assert_assembly
        rows=copy.deepcopy(self.rows); rows[0]['matrix'][1]=-0.0
        assert_assembly(rows,self.rows,{'斜撐':1})

    def test_missing_extra_or_suppressed_occurrence_fails(self):
        from solidworks_mcp.diagnostics.configuration_assembly_acceptance import assert_assembly
        for rows in ([],self.rows+[self.rows[0]], [self.rows[0]|{'suppressed':True}]):
            with self.subTest(rows=rows),self.assertRaises(AssertionError):
                assert_assembly(rows,self.rows,{'斜撐':1})

    def test_correct_equation_count_cannot_hide_moved_component(self):
        from solidworks_mcp.diagnostics.configuration_assembly_acceptance import assert_assembly
        rows=copy.deepcopy(self.rows);rows[0]['matrix'][10]=.01
        with self.assertRaisesRegex(AssertionError,'placement'):
            assert_assembly(rows,self.rows,{'斜撐':1})

    def test_invalid_matrix_and_referenced_configuration_fail(self):
        from solidworks_mcp.diagnostics.configuration_assembly_acceptance import assert_assembly
        for patch in ({'matrix':[0.]*15},{'matrix':[float('nan')]*16},{'configuration':'橫撐'}):
            with self.subTest(patch=patch),self.assertRaises(AssertionError):
                assert_assembly([self.rows[0]|patch],self.rows,{'斜撐':1})
