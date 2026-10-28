# Crash isolation for the MCP server process

A native fault in the Windows COM client inside the MCP server process (seen:
`combase.dll` access violation, null channel info in `CClientChannel::InitCallObject`
reached from `IDispatch::Invoke`) kills the server while SOLIDWORKS keeps
running, and the client loses the connection. See issue #6 on the fork.

## What was added
1. **Fault log** (`solidworks_mcp/crash_diag.py`): `faulthandler` writes the Python
   stack of every thread to `<server log>.fault.txt` (override with
   `SOLIDWORKS_MCP_FAULT_LOG`, `{server_pid}` is substituted). After a native
   crash it shows which tool or script line was running.
2. **Supervisor** (`solidworks_mcp_supervisor.py`, `solidworks_mcp/supervisor.py`):
   runs `solidworks_mcp_server.py` as a child process and relays MCP stdio. If the
   child dies, requests in flight get an error result naming the tool and the exit
   code, a new child starts and the original `initialize` handshake is replayed.
   More than `SOLIDWORKS_MCP_MAX_RESPAWNS` (default 5) restarts in 10 minutes
   closes the connection instead of looping.

## Use
Point the MCP client at `solidworks_mcp_supervisor.py` instead of
`solidworks_mcp_server.py` (same interpreter, same environment). Restart the MCP
connection after changing it.

## Behaviour after a crash
* The new worker connects to the configured PID like any fresh server; call
  `connect_solidworks` again. Per-session state of the old worker (open sketch,
  held `IFeature` references, unit setting) is gone.
* References held by the dead worker are released by COM rundown, which can
  destroy API wrappers that SOLIDWORKS still points to (see
  `IFEATURE_REFERENCE_KEEPALIVE.md`). After a worker crash, avoid `CloseDoc` on
  documents the old worker touched, or save and restart SOLIDWORKS.
* A native fault *inside* SOLIDWORKS is still handled by the native-fault marker.

## Tests
`tests/test_supervisor.py` uses a fake worker (crash exit code `0xC0000005`,
handshake replay, request-id preservation, restart limit). A smoke run through
the real server and an MCP client listed 27 tools and created the fault log.
Not covered: a real combase crash (cannot be forced on demand).
