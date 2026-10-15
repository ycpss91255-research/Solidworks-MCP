"""Refresh an unchanged equation without Delete/Add2 recreation.

The caller owns PID/document/configuration preflight and rebuild/geometry checks.
Use a freshly acquired typed IEquationMgr for the intended single configuration.
This helper never launches, saves, closes, retries or rolls back a CAD operation.
"""
import math


def refresh_existing_equation(manager, index, expected_text):
    if type(index) is not int or not isinstance(expected_text, str) or not expected_text:
        raise ValueError('Require an integer index and the exact existing equation text')
    before = [manager.Equation(i) for i in range(manager.GetCount())]
    if not 0 <= index < len(before) or before[index] != expected_text:
        raise ValueError('Equation index/text changed; inspect the document before updating')
    # This is a property put in pywin32; a None return is normal. Do not replace
    # it with Delete/Add2, which reproduces a native close fault in the mate flow.
    manager.SetEquation(index, expected_text)
    manager.EvaluateAll()
    value = manager.Value(index)
    status = manager.Status
    if not isinstance(status, int) or status < 0 or not math.isfinite(value):
        raise ValueError('Equation binding remains invalid after in-place refresh')
    after = [manager.Equation(i) for i in range(manager.GetCount())]
    if after != before:
        raise ValueError('Equation count, text or order changed during refresh')
    return {'index': index, 'equation': expected_text, 'value': value,
            'binding_status': status, 'equation_count_and_order_preserved': True}
