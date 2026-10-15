"""Exercise real stdio MCP processes with a fake CAD object; never connect CAD."""
from datetime import timedelta
import os
from pathlib import Path
import sys
import tempfile
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


FIXTURE = '''import asyncio,sys
from pathlib import Path
import pywintypes
from solidworks_mcp import server
from solidworks_mcp.native_fault import FaultStore
from solidworks_mcp.automation import managed_session
root=Path(sys.argv[1])
def audit(value):
 with (root/'cad-calls.txt').open('a',encoding='utf-8') as stream:stream.write(value+'\\n')
class FakeCad:
 @property
 def RevisionNumber(self):audit('RevisionNumber');return '31.5'
 @property
 def ActiveDoc(self):audit('ActiveDoc');return None
 def CloseDoc(self,title):
  audit('CloseDoc')
  raise pywintypes.com_error(-2147417851,'synthetic native fault',None,None)
 def Save3(self):audit('FORBIDDEN Save3');return True
managed_session.process_identity=lambda pid:'stdio-fixture-created'
automation=server.sw_automation
automation._target_pid='123';automation._configured_target='123'
automation._auto_launch=False;automation._connected=True
automation._bound_identity='stdio-fixture-created'
automation._recovery_startup_enabled=False
automation._fault_store=FaultStore(root/'faults')
automation._sw_app=FakeCad()
asyncio.run(server.main())
'''


class NativeFaultStdioTests(unittest.IsolatedAsyncioTestCase):
    async def test_fault_blocks_later_requests_and_survives_server_restart(self):
        await self.exercise_fault("sw.CloseDoc('private')")

    async def test_caught_fault_is_reported_and_blocks_after_restart(self):
        await self.exercise_fault("try:\n sw.CloseDoc('private')\nexcept Exception as error:\n print('sensor error',str(error))")

    async def exercise_fault(self, source):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / 'fake_cad_server.py'
            fixture.write_text(FIXTURE, encoding='utf-8')
            environment = dict(os.environ, SOLIDWORKS_AUTO_LAUNCH='0', SOLIDWORKS_RECOVERY_MONITOR='0',
                               SOLIDWORKS_MCP_LOG=str(root/'mcp.log'), SOLIDWORKS_SCRIPT_TRACE_DIR='')
            # Include this checkout even when the package is not installed editable.
            environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
            params = StdioServerParameters(command=sys.executable, args=[str(fixture), str(root)], env=environment)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=15)) as client:
                    await client.initialize()
                    failed = await client.call_tool('execute_python', {'code': source})
                    self.assertIn('[ERROR]', failed.content[0].text)
                    self.assertIn('-2147417851', failed.content[0].text)
                    before = (root/'cad-calls.txt').read_text()
                    blocked = await client.call_tool('execute_python', {'code': 'sw.Save3()'})
                    self.assertIn('native_fault_quarantined', blocked.content[0].text)
                    self.assertEqual((root/'cad-calls.txt').read_text(), before)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=15)) as client:
                    await client.initialize()
                    blocked = await client.call_tool('connect_solidworks', {})
                    self.assertIn('native_fault_quarantined', blocked.content[0].text)
                    blocked = await client.call_tool('execute_python', {'code': 'sw.Save3()'})
                    self.assertIn('native_fault_quarantined', blocked.content[0].text)
                    self.assertEqual((root/'cad-calls.txt').read_text(), before)


if __name__ == '__main__':
    unittest.main()
