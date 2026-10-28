"""Crash-isolating stdio supervisor for the MCP server.

The real server (``solidworks_mcp_server.py``) runs as a child process and
this module relays MCP's newline-delimited JSON-RPC between the client and the
child. All COM calls happen in the child, so a native crash there (for example
an access violation in ``combase.dll``) no longer drops the client connection:

* every request that was in flight gets an error result naming the tool and
  the exit code,
* a new child is started and the original ``initialize`` handshake is
  replayed, so the client keeps working without reconnecting,
* restarts are capped (default 5 in 10 minutes) to avoid a crash loop.

It uses only the standard library and never touches COM itself. The new child
reconnects to the configured SOLIDWORKS PID like any fresh server; the client
should call ``connect_solidworks`` again.
"""

import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import List, Optional

WINDOW_SECONDS = 600
INIT_TIMEOUT = 60


def worker_command() -> List[str]:
    raw = os.environ.get("SOLIDWORKS_MCP_WORKER_CMD")
    if raw:
        return list(json.loads(raw))
    entry = Path(__file__).resolve().parent.parent / "solidworks_mcp_server.py"
    return [sys.executable, str(entry)]


def describe_exit(code: Optional[int]) -> str:
    if code is None:
        return "unknown"
    return f"{code & 0xFFFFFFFF:#010x}" if code < 0 or code > 255 else str(code)


def error_response(request_id, method: str, tool: Optional[str], text: str) -> dict:
    if method == "tools/call":
        return {"jsonrpc": "2.0", "id": request_id,
                "result": {"content": [{"type": "text", "text": f"[ERROR] {text}"}],
                           "isError": True}}
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": text}}


class Supervisor:
    def __init__(self, command: List[str], out, max_respawns: int):
        self.command = command
        self.out = out
        self.max_respawns = max_respawns
        self.lock = threading.RLock()
        self.out_lock = threading.Lock()
        self.pending = {}
        self.child: Optional[subprocess.Popen] = None
        self.ready = threading.Event()
        self.init_done = threading.Event()
        self.init_request: Optional[dict] = None
        self.initialized_note: Optional[dict] = None
        self.respawns = deque()
        self.closing = False
        self.exit_code = 0
        self.generation = 0

    # -- output to the client ------------------------------------------------
    def emit(self, message) -> None:
        data = message if isinstance(message, bytes) else json.dumps(message, ensure_ascii=False).encode("utf-8")
        with self.out_lock:
            self.out.write(data.rstrip(b"\r\n") + b"\n")
            self.out.flush()

    # -- child management ----------------------------------------------------
    def spawn(self) -> subprocess.Popen:
        child = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=None, bufsize=0, env=os.environ.copy())
        self.generation += 1
        self.child = child
        threading.Thread(target=self._read_child, args=(child, self.generation), daemon=True).start()
        return child

    def _read_child(self, child: subprocess.Popen, generation: int) -> None:
        internal = f"sup-init-{generation}"
        for line in child.stdout:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except ValueError:
                self.emit(line)
                continue
            if isinstance(message, dict) and "method" not in message and "id" in message:
                if message["id"] == internal:
                    self.init_done.set()
                    continue
                with self.lock:
                    self.pending.pop(message["id"], None)
            self.emit(line)
        self._child_gone(child)

    def _child_gone(self, child: subprocess.Popen) -> None:
        code = child.wait()
        with self.lock:
            if self.closing or child is not self.child:
                return
            self.ready.clear()
            lost = list(self.pending.items())
            self.pending.clear()
            now = time.monotonic()
            self.respawns.append(now)
            while self.respawns and now - self.respawns[0] > WINDOW_SECONDS:
                self.respawns.popleft()
            giving_up = len(self.respawns) > self.max_respawns
        detail = f"worker process exited with code {describe_exit(code)}"
        for request_id, (method, tool) in lost:
            what = f" while running '{tool}'" if tool else ""
            text = (f"MCP worker crashed{what} ({detail}). "
                    + ("Restart limit reached; the MCP connection will close." if giving_up else
                       "SolidWorks was not touched by the supervisor. The worker was restarted; "
                       "call connect_solidworks again before continuing. Check the fault log next to the server log."))
            self.emit(error_response(request_id, method, tool, text))
        if giving_up:
            self.exit_code = 1
            self._shutdown()
            return
        self._restart()

    def _restart(self) -> None:
        with self.lock:
            self.init_done.clear()
            child = self.spawn()
            request, note = self.init_request, self.initialized_note
        if request is not None:
            replay = dict(request, id=f"sup-init-{self.generation}")
            self._write(child, replay)
            if not self.init_done.wait(INIT_TIMEOUT):
                self.exit_code = 1
                self._shutdown()
                return
            if note is not None:
                self._write(child, note)
        self.ready.set()

    @staticmethod
    def _write(child: subprocess.Popen, message) -> bool:
        data = message if isinstance(message, bytes) else json.dumps(message, ensure_ascii=False).encode("utf-8")
        try:
            child.stdin.write(data.rstrip(b"\r\n") + b"\n")
            child.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def _shutdown(self) -> None:
        self.closing = True
        if self.child is not None and self.child.poll() is None:
            self.child.kill()
        os._exit(self.exit_code)

    # -- client input --------------------------------------------------------
    def forward(self, line: bytes) -> None:
        try:
            message = json.loads(line)
        except ValueError:
            message = None
        if isinstance(message, dict):
            method = message.get("method")
            if method == "initialize":
                self.init_request = message
            elif method == "notifications/initialized":
                self.initialized_note = message
        is_request = isinstance(message, dict) and "method" in message and "id" in message
        # initialize itself is forwarded before the worker is marked ready
        if not (isinstance(message, dict) and message.get("method") == "initialize"):
            self.ready.wait(INIT_TIMEOUT * 2)
        with self.lock:
            child = self.child
            if is_request:
                params = message.get("params") or {}
                tool = params.get("name") if message["method"] == "tools/call" else None
                self.pending[message["id"]] = (message["method"], tool)
            alive = child is not None and child.poll() is None and self._write(child, line)
            if not alive and is_request:
                self.pending.pop(message["id"], None)
                self.emit(error_response(message["id"], message["method"], tool,
                                         "MCP worker is not running; it is being restarted, retry the call."))

    def run(self) -> int:
        self.spawn()
        self.ready.set()
        for line in sys.stdin.buffer:
            if line.strip():
                self.forward(line)
        self.closing = True
        child = self.child
        if child is not None:
            try:
                child.stdin.close()
            except OSError:
                pass
            try:
                child.wait(15)
            except subprocess.TimeoutExpired:
                child.kill()
        return self.exit_code


def main() -> int:
    limit = int(os.environ.get("SOLIDWORKS_MCP_MAX_RESPAWNS", "5"))
    return Supervisor(worker_command(), sys.stdout.buffer, limit).run()


if __name__ == "__main__":
    sys.exit(main())
