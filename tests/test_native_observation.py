"""Regression from event24437: fake CAD only, with temporary identity-bound markers."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import Mock,patch
import pywintypes
from solidworks_mcp import server
from solidworks_mcp.native_fault import FaultStore
from solidworks_mcp.automation.base import SolidWorksAutomation

class CaughtNativeFaultTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.identity=patch('solidworks_mcp.automation.managed_session.process_identity',return_value='synthetic-created')
  self.identity.start();self.addCleanup(self.identity.stop)
  self.a=SolidWorksAutomation();self.a._target_pid='123';self.a._configured_target='123'
  self.a._auto_launch=False;self.a._connected=True;self.a._bound_identity='synthetic-created'
  self.a._recovery_startup_enabled=False;self.a._fault_store=FaultStore(Path(self.tmp.name))
  self.a._sw_app=Mock();self.a._sw_app.ActiveDoc=None
  self.a._sw_app.GetSensorFeatureData.side_effect=pywintypes.com_error(-2147417851,'synthetic server fault',None,None)
 def execute(self,source):
  with patch.object(server,'sw_automation',self.a),patch.dict('os.environ',{'SOLIDWORKS_SCRIPT_TRACE_DIR':''}):
   return server._execute_python_fixed(source)
 def test_script_catching_native_error_must_not_report_success(self):
  result=self.execute("try:\n sw.GetSensorFeatureData()\nexcept Exception as ex:\n print('sensor error',str(ex))")
  self.assertFalse(result['success'],'A caught RPC_E_SERVERFAULT currently becomes false SUCCESS')
  self.assertIsNotNone(self.a._fault_store.read(123,lambda pid:'synthetic-created'))
 def test_caught_fault_blocks_next_save_without_health_probe(self):
  self.execute("try:\n sw.GetSensorFeatureData()\nexcept Exception:\n pass")
  result=self.execute('sw.Save3()')
  self.assertFalse(result['success'])
  self.a._sw_app.Save3.assert_not_called()
 def test_caught_ordinary_binding_error_does_not_quarantine(self):
  result=self.execute("try:\n raise TypeError('ordinary binding')\nexcept Exception:\n pass\nresult=42")
  self.assertTrue(result['success'])
  self.assertIsNone(self.a._fault_store.read(123,lambda pid:'synthetic-created'))


import sys,threading,json
from solidworks_mcp.native_observation import NativeFaultObservation

class ObservationTests(unittest.TestCase):
 def exercise(self,monitoring):
  a=Mock();error=pywintypes.com_error(-2147417851,'native fault',None,None)
  before=sys.gettrace()
  with self.assertRaises(pywintypes.com_error):
   with NativeFaultObservation(a,monitoring=monitoring):
    try:raise error
    except Exception:pass
  self.assertIs(sys.gettrace(),before)
  a.record_native_failure.assert_called_once_with(error)
 def test_monitoring_caught_fault(self):self.exercise(True)
 def test_fallback_caught_fault(self):self.exercise(False)
 def test_other_thread_native_error_is_not_attributed_to_this_cad(self):
  a=Mock()
  def work():
   try:raise pywintypes.com_error(-2147417851,'other thread',None,None)
   except Exception:pass
  with NativeFaultObservation(a):
   t=threading.Thread(target=work);t.start();t.join()
  a.record_native_failure.assert_not_called()
 def test_existing_trace_receives_events_and_is_restored(self):
  seen=[]
  def trace(frame,event,value):
   if frame.f_code.co_name=='work':seen.append(event)
   return trace
  def work():value=42;return value
  before=sys.gettrace();sys.settrace(trace)
  try:
   with NativeFaultObservation(Mock(),monitoring=False):self.assertEqual(work(),42)
   self.assertIs(sys.gettrace(),trace)
  finally:sys.settrace(before)
  self.assertIn('call',seen);self.assertIn('line',seen);self.assertIn('return',seen)
 def test_monitoring_slots_released_on_ordinary_exception(self):
  if not hasattr(sys,'monitoring'):self.skipTest('no monitoring API')
  before=[sys.monitoring.get_tool(i) for i in range(6)]
  with self.assertRaises(TypeError):
   with NativeFaultObservation(Mock()):raise TypeError('ordinary')
  self.assertEqual([sys.monitoring.get_tool(i) for i in range(6)],before)
 def test_full_monitoring_slots_fall_back_without_stealing_existing_tools(self):
  if not hasattr(sys,'monitoring'):self.skipTest('no monitoring API')
  occupied=[]
  try:
   for i in (3,4):
    if sys.monitoring.get_tool(i) is None:
     sys.monitoring.use_tool_id(i,'another-test-tool');occupied.append(i)
   before=[sys.monitoring.get_tool(i) for i in range(6)]
   self.exercise(True)
   self.assertEqual([sys.monitoring.get_tool(i) for i in range(6)],before)
  finally:
   for i in occupied:sys.monitoring.free_tool_id(i)

class TracedExecutionTests(CaughtNativeFaultTests):
 def execute(self,source):
  with tempfile.TemporaryDirectory() as directory,patch.object(server,'sw_automation',self.a),patch.dict('os.environ',{'SOLIDWORKS_SCRIPT_TRACE_DIR':directory}):
   response=server._execute_python_fixed(source)
   events=[json.loads(line)['event'] for p in Path(directory).glob('*.jsonl') for line in p.read_text().splitlines()]
   if response.get('data',{}).get('native_fault_quarantined') and not events:
    self.assertFalse(response['success'])
   else:
    self.assertIn('start',events)
    self.assertIn('failed' if not response['success'] else 'completed',events)
   return response

if __name__=='__main__':unittest.main(verbosity=2)
