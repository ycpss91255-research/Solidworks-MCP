"""Real MCP negative cases must leave all running SolidWorks processes intact."""
import asyncio
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from launch_solidworks import running_pids
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]

async def main():
    before = sorted(running_pids())
    cases = []
    for target in (None, '0'):
        env = dict(os.environ)
        env.pop('SOLIDWORKS_TARGET_PID', None)
        if target is not None:
            env['SOLIDWORKS_TARGET_PID'] = target
        env['SOLIDWORKS_MCP_LOG'] = str(ROOT/'test-results/no-launch-{server_pid}.log')
        params = StdioServerParameters(command=sys.executable,
            args=[str(ROOT/'solidworks_mcp_server.py')], env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=10)) as session:
                initialized = await session.initialize()
                assert 'never starts SolidWorks' in initialized.instructions
                result = await session.call_tool('connect_solidworks', {})
                response = result.content[0].text
                assert response.startswith('[ERROR]'), response
                cases.append({'target':target,'response':response})
        assert sorted(running_pids()) == before, 'SolidWorks process set changed'
    print(json.dumps({'passed':True, 'solidworks_pids_unchanged':before, 'cases':cases}, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
