"""Opt-in per-workspace lifecycle using the guarded instance launcher."""
import json
import os
from pathlib import Path
import time

import win32api
import win32con
import win32process


def process_identity(pid):
    try:
        handle = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
    except win32api.error as exc:
        if exc.winerror in (87, 1168):
            return None
        raise  # Access denied is not evidence the process has exited.
    try:
        executable = win32process.GetModuleFileNameEx(handle, 0)
        if Path(executable).name.casefold() != 'sldworks.exe':
            raise RuntimeError(f'PID {pid} now belongs to another application')
        return win32process.GetProcessTimes(handle)['CreationTime'].isoformat()
    finally:
        handle.Close()


def write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(state, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def connect_managed(automation):
    # Imported at runtime to share the same launch guard as the public CLI.
    from launch_solidworks import launcher_lock, _launch_locked
    from ..utils import find_solidworks
    session = os.environ.get('SOLIDWORKS_SESSION_FILE', '')
    if not session or not Path(session).is_absolute():
        raise ValueError('Managed startup requires an absolute SOLIDWORKS_SESSION_FILE')
    path = Path(session)
    configured = automation._configured_target
    pid = int(configured) if configured is not None else None
    if pid is not None and pid <= 0:
        raise ValueError('SOLIDWORKS_TARGET_PID must be positive')
    launched = False
    with launcher_lock():
        state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        if state and state.get('configured_pid') == configured:
            pid = int(state['pid'])
        else:
            state = None
        identity = process_identity(pid) if pid else None
        if state and identity and identity != state['start_time']:
            raise RuntimeError('Managed PID was reused; refusing to attach or launch')
        if identity is None:
            executable = find_solidworks()
            if not executable:
                raise RuntimeError('SolidWorks installation not found')
            pid = _launch_locked(executable)
            identity = process_identity(pid)
            if identity is None:
                raise RuntimeError(f'New SolidWorks PID {pid} exited during startup')
            state = {'pid':pid, 'start_time':identity, 'configured_pid':configured, 'ready':False}
            write_state(path, state)  # Reserve before waiting; retries cannot spawn duplicates.
            launched = True
        elif state is None:
            state = {'pid':pid, 'start_time':identity, 'configured_pid':configured, 'ready':True}
            write_state(path, state)
    automation._target_pid = str(pid)
    deadline = time.monotonic() + (45 if not state['ready'] else 0)
    while True:
        if process_identity(pid) != identity:
            raise RuntimeError(f'SolidWorks PID {pid} exited or changed during connection')
        result = automation._connect_target()
        if result['success'] or time.monotonic() >= deadline:
            break
        time.sleep(0.5)
    if result['success']:
        if not state['ready']:
            automation.app.UserControl = True
            automation.app.Visible = True
            state['ready'] = True
            with launcher_lock():
                current = json.loads(path.read_text(encoding='utf-8'))
                if current['pid'] == pid and current['start_time'] == identity:
                    write_state(path, state)
        result['data'].update(launched=launched, session_file=str(path))
    else:
        result['message'] += f'; PID {pid} remains the only target. No alternate instance launched.'
    return result
