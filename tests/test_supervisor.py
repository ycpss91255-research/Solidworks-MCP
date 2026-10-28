import json
import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent

WORKER = textwrap.dedent("""
    import json, os, sys
    boot = os.environ.get('FAKE_BOOT_FILE')
    n = 1
    if boot:
        p = open(boot, 'a+'); p.seek(0); n = len(p.read().split()) + 1; p.write('x '); p.close()
    for line in sys.stdin.buffer:
        m = json.loads(line)
        if m.get('method') == 'initialize':
            r = {'jsonrpc': '2.0', 'id': m['id'], 'result': {'boot': n, 'params': m['params']}}
        elif m.get('method') == 'notifications/initialized':
            continue
        elif m.get('method') == 'tools/call' and m['params']['name'] == 'crash':
            __import__('ctypes').windll.kernel32.ExitProcess(0xC0000005)
        else:
            r = {'jsonrpc': '2.0', 'id': m['id'], 'result': {'boot': n, 'echo': m['method']}}
        sys.stdout.buffer.write((json.dumps(r) + '\\n').encode()); sys.stdout.buffer.flush()
""")


class Client:
    def __init__(self, tmp_path, max_respawns=5):
        script = tmp_path / "worker.py"
        script.write_text(WORKER)
        env = dict(os.environ,
                   SOLIDWORKS_MCP_WORKER_CMD=json.dumps([sys.executable, str(script)]),
                   SOLIDWORKS_MCP_MAX_RESPAWNS=str(max_respawns),
                   FAKE_BOOT_FILE=str(tmp_path / "boots"))
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "solidworks_mcp_supervisor.py")],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env)
        self.next_id = 0

    def call(self, method, params=None, timeout=30):
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}})
        box = {}
        t = threading.Thread(target=lambda: box.update(line=self.proc.stdout.readline()), daemon=True)
        t.start()
        t.join(timeout)
        assert "line" in box, "no response"
        return json.loads(box["line"]) if box["line"] else None

    def send(self, message):
        self.proc.stdin.write((json.dumps(message) + "\n").encode())
        self.proc.stdin.flush()

    def close(self):
        self.proc.stdin.close()
        return self.proc.wait(30)


def handshake(c):
    r = c.call("initialize", {"protocolVersion": "x", "clientInfo": {"name": "t"}})
    c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return r


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._dir.name)
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            if c.proc.poll() is None:
                c.proc.kill()
            c.proc.stdin.close()
            c.proc.stdout.close()
        self._dir.cleanup()

    def client(self, max_respawns=5):
        c = Client(self.tmp, max_respawns)
        self.clients.append(c)
        return c

    def test_relays_requests(self):
        c = self.client()
        self.assertEqual(handshake(c)["result"]["boot"], 1)
        self.assertEqual(c.call("tools/list")["result"]["echo"], "tools/list")
        self.assertEqual(c.close(), 0)

    def test_crash_reports_tool_and_restarts_with_handshake_replayed(self):
        c = self.client()
        handshake(c)
        r = c.call("tools/call", {"name": "crash", "arguments": {}})
        self.assertTrue(r["result"]["isError"])
        text = r["result"]["content"][0]["text"]
        self.assertIn("'crash'", text)
        self.assertIn("0xc0000005", text)
        after = c.call("tools/list")
        self.assertEqual(after["result"]["boot"], 2)
        self.assertEqual(after["result"]["echo"], "tools/list")
        self.assertEqual(c.close(), 0)

    def test_request_id_is_preserved_on_crash(self):
        c = self.client()
        handshake(c)
        c.send({"jsonrpc": "2.0", "id": 99, "method": "tools/call", "params": {"name": "crash"}})
        first = json.loads(c.proc.stdout.readline())
        self.assertEqual(first["id"], 99)
        self.assertTrue(first["result"]["isError"])

    def test_restart_limit_closes_connection(self):
        c = self.client(max_respawns=1)
        handshake(c)
        c.call("tools/call", {"name": "crash"})
        self.assertEqual(c.call("tools/list")["result"]["boot"], 2)
        r = c.call("tools/call", {"name": "crash"})
        self.assertIn("limit", r["result"]["content"][0]["text"])
        self.assertEqual(c.proc.wait(30), 1)

    def test_describe_exit_formats_ntstatus(self):
        sys.path.insert(0, str(ROOT))
        from solidworks_mcp.supervisor import describe_exit
        self.assertEqual(describe_exit(3221225477), "0xc0000005")
        self.assertEqual(describe_exit(-1073741819), "0xc0000005")
        self.assertEqual(describe_exit(1), "1")


if __name__ == "__main__":
    unittest.main()
