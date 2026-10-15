import unittest
from unittest.mock import Mock
from solidworks_mcp.equation_binding import refresh_existing_equation


class EquationBindingTests(unittest.TestCase):
    def manager(self):
        formulas = ['"height"=200', '"D1@mate"="height"']
        manager = Mock()
        manager.GetCount.return_value = 2
        manager.Equation.side_effect = lambda index: formulas[index]
        manager.SetEquation.return_value = None  # property put, not an integer success code
        manager.Value.return_value = 200.0
        manager.Status = 1
        return manager

    def test_refresh_preserves_formula_and_order_without_delete_add(self):
        manager = self.manager()
        result = refresh_existing_equation(manager, 1, '"D1@mate"="height"')
        manager.SetEquation.assert_called_once_with(1, '"D1@mate"="height"')
        manager.EvaluateAll.assert_called_once()
        manager.Delete.assert_not_called()
        manager.Add2.assert_not_called()
        self.assertEqual(result['value'], 200.0)

    def test_stale_index_or_formula_never_updates_another_equation(self):
        manager = self.manager()
        with self.assertRaises(ValueError):
            refresh_existing_equation(manager, 0, '"D1@mate"="height"')
        manager.SetEquation.assert_not_called()

    def test_no_followup_api_after_native_setter_failure(self):
        manager = self.manager()
        manager.SetEquation.side_effect = RuntimeError('native server fault')
        with self.assertRaises(RuntimeError):
            refresh_existing_equation(manager, 1, '"D1@mate"="height"')
        manager.EvaluateAll.assert_not_called()
        manager.Value.assert_not_called()
        manager.Delete.assert_not_called()

    def test_invalid_binding_after_refresh_is_not_success(self):
        manager = self.manager()
        manager.Status = -1
        with self.assertRaises(ValueError):
            refresh_existing_equation(manager, 1, '"D1@mate"="height"')

    def test_reordered_equations_are_not_silently_accepted(self):
        manager = self.manager()
        manager.Equation.side_effect = ['"height"=200', '"D1@mate"="height"',
                                        '"D1@mate"="height"', '"height"=200']
        with self.assertRaises(ValueError):
            refresh_existing_equation(manager, 1, '"D1@mate"="height"')
