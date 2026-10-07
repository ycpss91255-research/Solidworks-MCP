import os
import unittest
from unittest.mock import MagicMock, patch

from solidworks_mcp.automation.base import SolidWorksAutomation


class TargetConnectionTests(unittest.TestCase):
    def setUp(self):
        # No unit test may initialize or query a real COM runtime.
        for name in ("CoInitialize", "CoUninitialize", "CreateBindCtx"):
            patcher = patch(f"pythoncom.{name}")
            patcher.start()
            self.addCleanup(patcher.stop)

    def automation(self, pid):
        with patch.dict(os.environ, {"SOLIDWORKS_TARGET_PID": pid}):
            return SolidWorksAutomation()

    def test_invalid_pid_never_falls_back(self):
        for pid in ("", "invalid", "0", "-1"):
            with self.subTest(pid=pid):
                sw = self.automation(pid)
                with patch("win32com.client.Dispatch") as fallback, patch("os.startfile") as launch:
                    self.assertFalse(sw.connect()["success"])
                    fallback.assert_not_called()
                    launch.assert_not_called()

    def test_selection_reconnect_and_missing_target(self):
        sw = self.automation("123")
        wrong, target = MagicMock(), MagicMock()
        wrong.GetDisplayName.return_value = "SolidWorks_PID_456"
        target.GetDisplayName.return_value = "SolidWorks_PID_123"
        rot = MagicMock()
        rot.EnumRunning.side_effect = [[wrong, target], [wrong]]
        app = MagicMock()
        app.GetProcessID.return_value = 123
        app.RevisionNumber.return_value = "33"
        with patch("pythoncom.GetRunningObjectTable", return_value=rot), patch("win32com.client.Dispatch", return_value=app), patch("win32com.client.GetActiveObject") as fallback, patch("os.startfile") as launch:
            self.assertEqual(sw.connect()["data"]["pid"], 123)
            rot.GetObject.assert_called_once_with(target)
            sw.disconnect()
            self.assertFalse(sw.connect()["success"])
            self.assertIsNone(sw.app)
            fallback.assert_not_called()
            launch.assert_not_called()

    def test_identity_mismatch_rejected(self):
        sw = self.automation("123")
        target = MagicMock()
        target.GetDisplayName.return_value = "SolidWorks_PID_123"
        rot = MagicMock()
        rot.EnumRunning.return_value = [target]
        app = MagicMock()
        app.GetProcessID.return_value = 456
        with patch("pythoncom.GetRunningObjectTable", return_value=rot), patch("win32com.client.Dispatch", return_value=app):
            self.assertFalse(sw.connect()["success"])
            self.assertIsNone(sw.app)

    def test_missing_environment_never_launches(self):
        with patch.dict(os.environ, {}, clear=True):
            sw = SolidWorksAutomation()
        with patch('win32com.client.Dispatch') as dispatch, \
             patch('win32com.client.GetActiveObject') as active, \
             patch('os.startfile') as launch, \
             patch('pythoncom.GetRunningObjectTable') as rot:
            result = sw.connect()
            self.assertFalse(result['success'])
            self.assertIn('SOLIDWORKS_TARGET_PID is required', result['message'])
            for operation in (dispatch, active, launch, rot):
                operation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
