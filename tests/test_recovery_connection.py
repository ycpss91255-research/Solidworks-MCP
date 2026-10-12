import unittest,asyncio
from unittest.mock import Mock,patch
from solidworks_mcp.automation.base import SolidWorksAutomation

class RecoveryConnectionTests(unittest.TestCase):
    def automation(self,success=True):
        instance=object.__new__(SolidWorksAutomation)
        instance._auto_launch=False;instance._target_pid='123'
        instance._recovery_startup_enabled=True;instance._recovery_monitor_error=None
        instance._connect_target=Mock(return_value={'success':success,'data':{'pid':123}})
        return instance
    def test_successful_attach_starts_recovery_at_base_connection(self):
        instance=self.automation()
        with patch('solidworks_mcp.recovery_service.ensure_recovery_worker',return_value={'worker_pid':456}) as start:
            result=instance.connect()
        start.assert_called_once_with(123)
        self.assertEqual(result['data']['recovery_monitor']['worker_pid'],456)
    def test_failed_com_connection_never_starts_recovery(self):
        instance=self.automation(False)
        with patch('solidworks_mcp.recovery_service.ensure_recovery_worker') as start:
            self.assertFalse(instance.connect()['success'])
        start.assert_not_called()
    def test_worker_connection_cannot_recursively_launch_workers(self):
        instance=self.automation();instance._recovery_startup_enabled=False
        with patch('solidworks_mcp.recovery_service.ensure_recovery_worker') as start:
            self.assertTrue(instance.connect()['success'])
        start.assert_not_called()
    def test_managed_connection_uses_its_resolved_pid(self):
        instance=self.automation();instance._auto_launch=True
        with patch('solidworks_mcp.automation.managed_session.connect_managed',return_value={'success':True,'data':{'pid':999}}), \
             patch('solidworks_mcp.recovery_service.ensure_recovery_worker',return_value={'worker_pid':456}) as start:
            instance.connect()
        start.assert_called_once_with(999);instance._connect_target.assert_not_called()
    def test_recovery_failure_is_visible_without_claiming_worker_started(self):
        instance=self.automation()
        with patch('solidworks_mcp.recovery_service.ensure_recovery_worker',side_effect=RuntimeError('worker failed')):
            result=instance.connect()
        self.assertEqual(result['data']['recovery_monitor_error'],'worker failed')
        self.assertNotIn('recovery_monitor',result['data'])
        self.assertEqual(instance._recovery_monitor_error,'worker failed')
    def test_implicit_cad_tool_response_surfaces_recovery_error(self):
        from solidworks_mcp import server
        with patch.object(server.sw_automation,'_recovery_monitor_error','worker failed'), \
             patch.object(server.sw_automation,'create_recovery_snapshot',return_value={
                 'success':True,'message':'copy','error_code':0,'error_name':'swSuccess'}):
            result=asyncio.run(server.call_tool('create_recovery_snapshot',{'directory':'C:/private'}))
        self.assertIn('recovery_monitor_error',result[0].text)
    def test_connected_worker_failure_refreshes_on_tool_response(self):
        from solidworks_mcp import server
        with patch.object(server.sw_automation,'_recovery_worker',{'worker_pid':456},create=True), \
             patch('solidworks_mcp.recovery_service.recovery_worker_error',return_value='Recovery monitor failed: save error') as health, \
             patch.object(server.sw_automation,'create_recovery_snapshot',return_value={
                 'success':True,'message':'copy','error_code':0,'error_name':'swSuccess'}):
            result=asyncio.run(server.call_tool('create_recovery_snapshot',{'directory':'C:/private'}))
        health.assert_called_once()
        self.assertIn('Recovery monitor failed: save error',result[0].text)

if __name__=='__main__':unittest.main()
