"""Native-crash diagnostics for the MCP server process.

A fault inside the Windows COM client (for example ``combase.dll`` access
violations) kills the process without a Python traceback. ``faulthandler``
writes the Python stack of every thread to a file when that happens, so the
tool call or script line that was running can be identified afterwards.
"""

import faulthandler
import os
import time
from pathlib import Path
from typing import Optional

_fault_file = None


def fault_log_path(log_file: Path, pid: Optional[int] = None) -> Path:
    """Path of the fault log belonging to a server log file."""
    override = os.environ.get("SOLIDWORKS_MCP_FAULT_LOG")
    if override:
        return Path(override.replace("{server_pid}", str(pid or os.getpid())))
    return Path(str(log_file) + ".fault.txt")


def enable_fault_log(log_file: Path) -> Optional[Path]:
    """Enable ``faulthandler`` into a file next to the server log.

    Returns the path, or ``None`` when it could not be enabled (diagnostics
    must never stop the server from starting).
    """
    global _fault_file
    if _fault_file is not None:
        return Path(_fault_file.name)
    try:
        path = fault_log_path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        _fault_file = open(path, "a", encoding="utf-8", buffering=1)
        _fault_file.write(f"--- server pid {os.getpid()} started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        faulthandler.enable(file=_fault_file, all_threads=True)
        return path
    except Exception:
        _fault_file = None
        return None
