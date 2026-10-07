"""Verify desktop child survives MCP-style kill-on-close job cleanup.

Uses only disposable Python processes; never starts or attaches to CAD.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import win32api
import win32con
import win32event
import win32job

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as folder:
        result = Path(folder) / 'child.json'
        gate = Path(folder) / 'go'
        script = Path(folder) / 'server.py'
        script.write_text(
            'import sys,time,json\nfrom pathlib import Path\n'
            f'sys.path.insert(0,{str(ROOT)!r})\n'
            'from solidworks_mcp.desktop_process import start_desktop_process\n'
            f'gate=Path({str(gate)!r})\n'
            'while not gate.exists(): time.sleep(0.05)\n'
            f"pid=start_desktop_process({sys._base_executable!r},Path.cwd(),['-c','import time; time.sleep(60)'])\n"
            f'Path({str(result)!r}).write_text(json.dumps({{"pid":pid}}))\n'
            'time.sleep(60)\n', encoding='utf-8')
        job = win32job.CreateJobObject(None, '')
        limits = win32job.QueryInformationJobObject(job, win32job.JobObjectExtendedLimitInformation)
        limits['BasicLimitInformation']['LimitFlags'] |= win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(job, win32job.JobObjectExtendedLimitInformation, limits)
        server = subprocess.Popen([sys._base_executable, str(script)], creationflags=subprocess.CREATE_NO_WINDOW)
        child_handle = None
        try:
            handle = win32api.OpenProcess(0x100 | 0x1, False, server.pid)
            try:
                win32job.AssignProcessToJobObject(job, handle)
            finally:
                handle.Close()
            gate.touch()
            deadline = time.monotonic() + 15
            while not result.exists() and time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError('Disposable server exited before launch')
                time.sleep(0.1)
            pid = json.loads(result.read_text())['pid']
            print('Fixture child PID:', pid, 'server PID:', server.pid, flush=True)
            child_handle = win32api.OpenProcess(win32con.SYNCHRONIZE | win32con.PROCESS_TERMINATE, False, pid)
            job.Close()
            job = None
            server.wait(timeout=5)
            assert win32event.WaitForSingleObject(child_handle, 1000) == win32con.WAIT_TIMEOUT
            print(json.dumps({'server_killed': True, 'desktop_child_survived': True, 'cad_touched': False}))
        finally:
            if child_handle:
                win32api.TerminateProcess(child_handle, 0)
                child_handle.Close()
            if job:
                job.Close()
            if server.poll() is None:
                server.terminate()
            server.wait(timeout=5)


if __name__ == '__main__':
    main()
