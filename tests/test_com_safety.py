import unittest
from unittest.mock import Mock, patch
import win32com.client
from solidworks_mcp.com_safety import MODEL_EXTENSION_IID, install_dependency_query_guard


class DependencyGuardTests(unittest.TestCase):
    def test_faulting_method_is_blocked_before_invoke_and_other_calls_forward(self):
        original = Mock(return_value='native-result')
        # Mock attributes must not look like an installed guard.
        original._solidworks_dependency_guard = False
        with patch.object(win32com.client.DispatchBaseClass, '_ApplyTypes_', original):
            install_dependency_query_guard()
            guarded = win32com.client.DispatchBaseClass._ApplyTypes_
            obj = type('Extension', (), {'CLSID': MODEL_EXTENSION_IID})()
            with self.assertRaisesRegex(RuntimeError, 'native sldapiu.dll'):
                guarded(obj,306,1,(12,0),(), 'GetDependencies',None,True,True,False,True,True)
            original.assert_not_called()
            self.assertEqual(guarded(obj,307,1,(12,0),(),'OtherMethod',None), 'native-result')
            unrelated = type('Other', (), {'CLSID':'{OTHER}'})()
            self.assertEqual(guarded(unrelated,306,1,(12,0),(),'GetDependencies',None), 'native-result')
            install_dependency_query_guard()
            self.assertIs(win32com.client.DispatchBaseClass._ApplyTypes_, guarded)
