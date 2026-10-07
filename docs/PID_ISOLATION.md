# PID-bound connections and low-memory warning handling

Start a separate SolidWorks instance, then configure a separate MCP server
with `SOLIDWORKS_TARGET_PID` set to its current process ID. The server binds
only to the exact `SolidWorks_PID_<pid>` Running Object Table entry and verifies
the returned process ID. Missing, invalid, or unavailable targets fail without
launching SolidWorks or connecting to another instance. With this variable
unset, the existing connection behavior is preserved.

Set `SOLIDWORKS_MCP_LOG` to a separate log file for each MCP server.
For example, an MCP client configuration can use:

```json
{
  "mcpServers": {
    "solidworks-test": {
      "command": "C:/tools/solidworks-mcp/.venv/Scripts/python.exe",
      "args": ["C:/tools/solidworks-mcp/solidworks_mcp_server.py"],
      "env": {
        "SOLIDWORKS_TARGET_PID": "12345",
        "SOLIDWORKS_MCP_LOG": "C:/logs/solidworks-test.log"
      }
    }
  }
}
```

Replace the paths and PID with the actual values. Restart the MCP connection
after changing its environment. Update the PID after restarting SolidWorks.
Install `requirements.txt` in the separate server's Python environment.

## Low-memory warning during open_document

The optional `memory_warning_action` argument controls this specific warning:

| Value | Behavior |
| --- | --- |
| `manual` (default) | Leave the warning for the user. |
| `continue` | Press Yes and continue opening. |
| `cancel` | Press No and cancel opening. |

```json
{"filepath":"C:/models/example.SLDPRT","memory_warning_action":"continue"}
```

Automatic handling requires `SOLIDWORKS_TARGET_PID`. During `OpenDoc6`, a
watcher identifies visible SOLIDWORKS task dialogs in that process, reads
their text through Windows UI Automation, and verifies both Yes/No buttons.
It recognizes Traditional Chinese, Simplified Chinese, and English low-memory
messages. It posts the documented `TDM_CLICK_BUTTON` message only after
rechecking the target. A held process handle prevents targeting a reused PID.
The watcher handles at most one warning and monitors for up to 30 seconds.
It does not use foreground changes, global keyboard input, or coordinates.

The response includes `memory_warning_events` (including action and whether
closure was observed) and `memory_warning_handler_errors`. Other dialogs are
left untouched. Warnings outside this open operation are not handled. This
does not fix memory shortages or suppress subsequent warnings.

PID binding isolates COM routing, not shared RAM, installation settings, or
per-user journal/AutoRecover resources. Arbitrary `execute_python` code can
still obtain other COM objects; PID binding is not a security sandbox.

## Verification

On Windows with dependencies installed:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/verify_memory_warning_native.py
```

The native test opens disposable helper task dialogs, checks Yes/No return
values and closure, and verifies a separate identical dialog is untouched.
It never attaches to SolidWorks. Output is written under ignored `test-results/`.

Observed validation on SolidWorks 2023 includes PID-bound real MCP connection,
sketch/circle/extrusion, measured solid volume, save/close, reopened file readback,
and reconnect. An actual low-memory warning was recognized read-only; it was
manually dismissed by the user. Automatic dismissal of an actual SolidWorks
warning remains unverified. Native task-dialog tests passed for both actions.
The existing default part-template search also missed a Chinese template;
explicit template selection worked. This change does not fix template search.
