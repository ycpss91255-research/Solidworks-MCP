"""Guarded launcher and existing-PID verifier, also used by opt-in managed MCP."""
import argparse
import ctypes
from ctypes import wintypes
import json
import logging
import os
from pathlib import Path
import time
from contextlib import contextmanager

import win32api
import win32process
import win32event
import win32con
import win32file

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.utils import find_solidworks
from solidworks_mcp.desktop_process import start_desktop_process


def running_pids():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel.QueryFullProcessImageNameW
    query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                      ctypes.POINTER(wintypes.DWORD)]
    query.restype = wintypes.BOOL
    found = []
    for pid in win32process.EnumProcesses():
        try:
            handle = win32api.OpenProcess(0x1000, False, pid)
            try:
                buffer = ctypes.create_unicode_buffer(32768)
                length = wintypes.DWORD(len(buffer))
                if query(int(handle), 0, buffer, ctypes.byref(length)):
                    if Path(buffer.value).name.casefold() == 'sldworks.exe':
                        found.append(pid)
            finally:
                handle.Close()
        except win32api.error:
            continue
    return found


@contextmanager
def launcher_lock():
    mutex = win32event.CreateMutex(None, False, 'Local\\SolidWorksMCPLauncher')
    acquired = False
    try:
        status = win32event.WaitForSingleObject(mutex, 5000)
        acquired = status in (win32con.WAIT_OBJECT_0, win32con.WAIT_ABANDONED)
        if not acquired:
            raise RuntimeError('Another launcher is busy; no process was launched')
        yield
    finally:
        if acquired:
            win32event.ReleaseMutex(mutex)
        mutex.Close()


def launch(executable):
    with launcher_lock():
        return _launch_locked(executable)


def launch_journal_experiment(executable, folder, evidence, on_launch=None):
    """Explicit experiment, not the default or managed-MCP launch policy."""
    from solidworks_mcp.journal_registry import JournalFolderLease
    from solidworks_mcp.process_files import journal_handles
    folder = Path(folder)
    evidence = Path(evidence)
    if not folder.is_absolute() or not evidence.is_absolute():
        raise ValueError('Experiment folder and evidence must be absolute')
    if folder.exists() and any(folder.iterdir()):
        raise ValueError('Experiment requires a new, empty journal folder')
    executable = Path(executable).resolve(strict=True)
    if executable.name.casefold() != 'sldworks.exe':
        raise ValueError('Expected the installed SLDWORKS.exe')
    version = win32api.GetFileVersionInfo(str(executable), '\\')['FileVersionMS'] >> 16
    if version < 10 or version > 100:
        raise ValueError('Unrecognized SolidWorks executable version')
    key_path = rf'Software\SolidWorks\SOLIDWORKS {version + 1992}\ExtReferences'
    with launcher_lock():
        before = running_pids()
        baseline = journal_handles(before)
        with JournalFolderLease(key_path, folder, evidence) as lease:
            lease.state['preserved_journal_handles'] = baseline
            pid = _launch_locked(executable)
            if on_launch:
                on_launch(pid)
            lease.state['launched_pid'] = pid
            lease._record('waiting_for_journal')
            deadline = time.monotonic() + 45
            while True:
                if pid not in running_pids():
                    raise RuntimeError(f'Experiment PID {pid} exited; do not launch an alternate')
                rows = journal_handles([pid, *before])
                own = [row for row in rows if row['pid'] == pid and
                       Path(row['path']).resolve() == (folder / 'swxJRNL.swj').resolve()]
                if own:
                    if any(row not in rows for row in baseline):
                        raise RuntimeError('An existing journal handle changed during experiment')
                    lease.state['verified_journal_handles'] = rows
                    lease._record('journal_opened')
                    break
                if time.monotonic() >= deadline:
                    lease.state['observed_journal_handles'] = rows
                    raise RuntimeError(f'PID {pid} did not open its assigned journal. '
                                       'Registry will be restored; keep this PID for diagnosis.')
                time.sleep(0.5)
        return pid


def launch_session(executable, session_file, journal_dir=None, journal_evidence=None, journal_redirect=None):
    """Reuse only this session's recorded live process; never cap other sessions."""
    from solidworks_mcp.automation.managed_session import process_identity, write_state
    path = Path(session_file)
    if not path.is_absolute():
        raise ValueError('An absolute per-session file is required')
    with launcher_lock():
        if path.exists():
            state = json.loads(path.read_text(encoding='utf-8'))
            identity = process_identity(int(state['pid']))
            if identity:
                if identity != state['start_time']:
                    raise RuntimeError('Session PID was reused; refusing to attach or launch')
                return int(state['pid']), False

        if journal_redirect:
            if len(journal_redirect) not in (3,4):
                raise ValueError('Journal routing requires three paths')
            dll, source, destination = map(Path, journal_redirect[:3])
            if not all(Path(p).is_absolute() for p in journal_redirect):
                raise ValueError('Journal routing paths must be absolute')
            if not dll.is_file() or not source.is_dir():
                raise ValueError('Journal routing DLL and source directory must exist')
            if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
                raise ValueError('Journal routing requires a new, empty private directory')
            if source.resolve() == destination.resolve():
                raise ValueError('Journal routing source and destination must differ')
            if len(journal_redirect)==4:
                recovery=Path(journal_redirect[3])
                if recovery.resolve().is_relative_to(source.resolve()) or recovery.resolve()==destination.resolve():
                    raise ValueError('Recovery routing requires a separate directory outside the shared journal folder')
                if recovery.exists() and (not recovery.is_dir() or any(recovery.iterdir())):
                    raise ValueError('Recovery routing requires a new, empty private directory')

        def reserve(pid):
            identity = process_identity(pid)
            if not identity:
                raise RuntimeError(f'New PID {pid} exited during startup')
            write_state(path, {'pid':pid, 'start_time':identity,
                              'configured_pid':None, 'ready':False})

        if journal_dir:
            pid = launch_journal_experiment(executable, journal_dir, journal_evidence, reserve)
        else:
            pid = _launch_locked(executable, journal_redirect) if journal_redirect else _launch_locked(executable)
            reserve(pid)
        return pid, True


def _launch_locked(executable, journal_redirect=None):
    executable = Path(executable).resolve(strict=True)
    if executable.name.casefold() != 'sldworks.exe':
        raise ValueError('Expected the installed SLDWORKS.exe')
    for notice in check_journal_available():
        logging.getLogger(__name__).warning(notice)
    if journal_redirect:
        from solidworks_mcp.journal_redirect_bootstrap import initialize_created
        dll, source, destination = journal_redirect[:3]
        def before_resume(process,pid):
            initialize_created(process,pid,dll,source,destination,
                               journal_redirect[3] if len(journal_redirect)==4 else None)
        return start_desktop_process(executable, executable.parent, before_resume=before_resume)
    return start_desktop_process(executable, executable.parent)


def check_journal_available():
    """Return nonfatal sharing notices; never change shared registry settings."""
    import winreg
    roots = Path(os.environ['APPDATA']) / 'SOLIDWORKS'
    candidates = set(roots.glob('SOLIDWORKS */swxJRNL.swj'))
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\SolidWorks') as root:
            for index in range(winreg.QueryInfoKey(root)[0]):
                version = winreg.EnumKey(root, index)
                if not version.upper().startswith('SOLIDWORKS '):
                    continue
                try:
                    with winreg.OpenKey(root, version + r'\ExtReferences') as refs:
                        folders, _ = winreg.QueryValueEx(refs, 'SolidWorks Journal Folders')
                        for folder in folders.split(';'):
                            if folder:
                                candidates.add(Path(os.path.expandvars(folder)) / 'swxJRNL.swj')
                except FileNotFoundError:
                    pass
    except FileNotFoundError:
        pass
    notices = []
    for path in candidates:
        if not path.exists():
            continue
        try:
            handle = win32file.CreateFile(str(path), win32con.GENERIC_READ, 0,
                                         None, win32con.OPEN_EXISTING, 0, None)
        except win32api.error as exc:
            if exc.winerror == 32:
                notices.append(f'Journal file is already in use: {path}. '
                               'Launching an independent PID is allowed; SolidWorks may '
                               'show a journal/AutoRecover warning. Shared settings were not changed.')
                continue
            raise RuntimeError(f'Journal file unavailable: {path} (Windows error {exc.winerror}). '
                               'No process was launched. PID isolation does not isolate '
                               'per-user journal/AutoRecover files.') from exc
        else:
            handle.Close()
    return notices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pid', type=int, help='Verify an existing instance without launching')
    mode.add_argument('--launch', action='store_true', help='Explicitly request one new instance')
    parser.add_argument('--exe', help='Installed SLDWORKS.exe path (optional)')
    parser.add_argument('--output', type=Path, help='Write the verified connection manifest')
    parser.add_argument('--session-file', type=Path, help='Absolute state file owned by this chat; prevents duplicate startup')
    parser.add_argument('--journal-warning-action', choices=('manual','dismiss'), default='manual', help='Explicitly dismiss only the new PID journal/AutoRecover warning')
    parser.add_argument('--journal-redirect-dll', type=Path, help='Experimental process-only journal routing DLL; new process only')
    parser.add_argument('--journal-source-dir', type=Path, help='Exact original journal directory for experimental routing')
    parser.add_argument('--journal-private-dir', type=Path, help='New empty private journal directory for experimental routing')
    parser.add_argument('--recovery-private-dir', type=Path, help='Experimental process-local AutoRecover directory; requires journal routing')
    parser.add_argument('--journal-dir', type=Path, help='Experimental unique journal folder; changes and restores the per-user registry value')
    parser.add_argument('--journal-evidence', type=Path, help='Required absolute backup/evidence path for --journal-dir')
    args = parser.parse_args()
    if bool(args.journal_dir) != bool(args.journal_evidence) or (args.journal_dir and not args.launch):
        parser.error('Journal experiment requires --launch, --journal-dir and --journal-evidence together')
    session_file = args.session_file or (args.output.with_suffix('.session.json') if args.output else None)
    if args.launch and not session_file:
        parser.error('--launch requires --session-file or --output belonging to this chat')
    redirect_parts=(args.journal_redirect_dll,args.journal_source_dir,args.journal_private_dir)
    if args.recovery_private_dir and not all(redirect_parts):
        parser.error('--recovery-private-dir requires all journal routing arguments')
    if any(redirect_parts) and (not all(redirect_parts) or not args.launch or args.journal_dir):
        parser.error('Journal routing experiment requires --launch and all three routing arguments')
    if all(redirect_parts):
        if not all(path.is_absolute() for path in redirect_parts):
            parser.error('Journal routing experiment paths must be absolute')
        if args.journal_private_dir.exists() and any(args.journal_private_dir.iterdir()) and not session_file.exists():
            parser.error('Journal routing experiment requires a new, empty private directory')
    pid = args.pid
    if args.launch:
        executable = args.exe or find_solidworks()
        if not executable:
            raise RuntimeError('SolidWorks installation not found; no process was launched')
        routing=(redirect_parts+(args.recovery_private_dir,) if args.recovery_private_dir else redirect_parts)
        pid, launched = launch_session(executable, session_file, args.journal_dir, args.journal_evidence,
                                       routing if all(redirect_parts) else None)
        print(f'{"Launched" if launched else "Reused"} this session instance: PID {pid}', flush=True)
    if not pid or pid <= 0:
        raise ValueError('A positive PID is required')
    os.environ['SOLIDWORKS_TARGET_PID'] = str(pid)
    automation = SolidWorksAutomation()
    # CLI verification must inspect exactly --pid/the PID it just launched,
    # even when the parent shell inherited a managed workspace environment.
    automation._auto_launch = False
    from contextlib import nullcontext
    from solidworks_mcp.automation.journal_warning import JournalWarningHandler
    warning = (JournalWarningHandler(pid, 60) if args.launch and args.journal_warning_action == 'dismiss'
               else nullcontext())
    try:
        deadline = time.monotonic() + (60 if args.launch else 0)
        with warning:
            while True:
                result = automation.connect()
                if result['success'] or time.monotonic() >= deadline:
                    break
                time.sleep(0.5)
            if args.launch and args.journal_warning_action == 'dismiss':
                if result['success']:
                    automation.app.UserControl = True
                    automation.app.Visible = True
                # Startup warnings can follow COM registration; keep the scoped
                # watcher alive briefly instead of treating connect as UI proof.
                warning.stop.wait(2)
        if not result['success']:
            raise RuntimeError(f'PID {pid}: {result["message"]}. '
                               'No alternate instance was launched; inspect this instance.')
        if args.launch:
            automation.app.UserControl = True
            automation.app.Visible = True
            from solidworks_mcp.automation.managed_session import write_state
            state = json.loads(session_file.read_text(encoding='utf-8'))
            state['ready'] = True
            write_state(session_file, state)
        root = Path(__file__).resolve().parent
        manifest = {'pid': pid, 'command': str(root/'.venv/Scripts/python.exe'),
                    'args': [str(root/'solidworks_mcp_server.py')],
                    'env': {'SOLIDWORKS_TARGET_PID': str(pid),
                            'SOLIDWORKS_MCP_LOG': str(root/f'test-results/session-{pid}-{{server_pid}}.log')}}
        if args.launch and args.journal_warning_action == 'dismiss':
            manifest['journal_warning_events'] = warning.events
            manifest['journal_warning_errors'] = warning.errors
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(json.dumps(manifest, indent=2))
    finally:
        automation.disconnect()


if __name__ == '__main__':
    main()
