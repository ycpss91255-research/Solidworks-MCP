"""Rewrite SOLIDWORKS references of closed files in a moved or copied tree from an old root to a new root.

Dry run by default. Nothing is opened; only files under --new-root are changed. See docs/REFERENCE_REBASE.md.

  python rebase_references.py --old-root C:/repo/wt-a --new-root D:/moved/wt-b --pid 12345
  python rebase_references.py --old-root C:/repo/wt-a --new-root D:/moved/wt-b --launch --session-file C:/me/own.json --apply --report out.json

--pid attaches to an existing instance (PID-bound, never discovers or launches another). --launch starts one chat-owned
instance through the guarded launcher (requires --session-file), waits for the resource gate, and retires only that
instance, through a held handle, when it is done."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from solidworks_mcp import reference_rebase as rr


def wait_for_resources(minutes):
    from solidworks_mcp.diagnostics.resource_wait import resource_ready
    from solidworks_mcp.script_trace import memory_snapshot
    deadline = time.monotonic() + minutes * 60
    while True:
        samples = []
        for attempt in range(3):
            samples.append(memory_snapshot())
            if not resource_ready(samples[-1], max_commit=95, min_available_mb=6144, min_commit_reserve_mb=6144):
                break
            if attempt < 2:
                time.sleep(5)
        else:
            return
        if time.monotonic() >= deadline:
            raise SystemExit('Resource gate stayed below the launch threshold; no instance was started.')
        time.sleep(60)


def launch(session_file, wait_minutes, journal_action):
    import win32api, win32con, win32process
    session = Path(session_file)
    if not session.is_absolute() or session.exists():
        raise SystemExit('--session-file must be an absolute path to a NEW chat-owned file')
    wait_for_resources(wait_minutes)
    done = subprocess.run([sys.executable, '-B', str(ROOT / 'launch_solidworks.py'), '--launch', '--session-file', str(session),
                           '--journal-warning-action', journal_action], cwd=ROOT, capture_output=True, text=True, errors='replace',
                          creationflags=subprocess.CREATE_NO_WINDOW)
    if done.returncode != 0:
        raise SystemExit('Launch failed: ' + (done.stdout + done.stderr)[-400:])
    state = json.loads(session.read_text(encoding='utf-8'))
    held = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE, False, state['pid'])
    started = win32process.GetProcessTimes(held)['CreationTime'].timestamp()
    if abs(started - datetime.fromisoformat(state['start_time']).timestamp()) > .01:
        raise SystemExit('Launched process identity does not match its session file')
    return state['pid'], held


def connect(pid):
    os.environ['SOLIDWORKS_TARGET_PID'] = str(pid)
    os.environ['SOLIDWORKS_AUTO_LAUNCH'] = '0'
    from solidworks_mcp.automation.base import SolidWorksAutomation
    automation = SolidWorksAutomation()
    automation._auto_launch = False
    automation._recovery_startup_enabled = False
    result = automation.connect()
    if not result['success']:
        raise SystemExit(f'Cannot attach to PID {pid}: {result["message"]}')
    from win32com.client import gencache
    module = gencache.EnsureModule('{83A33D31-27C5-11CE-BFD4-00400513BB57}', 0, 31, 0)
    app = module.ISldWorks(automation.app._oleobj_)
    if app.GetProcessID() != pid:
        raise SystemExit('Attached process does not match the requested PID')
    return app


def retire(app, held):
    import win32event
    if app.GetFirstDocument():
        print('Not exiting the owned instance: a document is open.', file=sys.stderr)
        return None
    app.ExitApp()
    if win32event.WaitForSingleObject(held, 60000) != win32event.WAIT_OBJECT_0:
        print('The owned instance did not exit within 60 s; it was left running.', file=sys.stderr)
        return None
    import win32process
    return win32process.GetExitCodeProcess(held)


def summarize(report):
    counts = report['counts']
    print(f"mode: {report['mode']}   files scanned: {report['files']}   locked (skipped): {len(report['locked_skipped'])}")
    print('references: ' + ', '.join(f'{k}={v}' for k, v in counts.items()))
    if report['mode'] == 'apply':
        print(f"replaced: {report['replaced']}   failed: {len(report['failed'])}   still pointing at the old root: "
              f"{len(report['remaining_old'])}   verified: {report['verified']}")
    for label, status in (('would replace' if report['mode'] == 'dry-run' else 'replaced', 'replace'),
                          ('NO FILE AT THE NEW LOCATION', 'missing_target'), ('outside both roots (left alone)', 'outside')):
        rows = [a for a in report['actions'] if a['status'] == status]
        for a in rows[:12]:
            print(f"  [{label}] {Path(a['file']).name}: {a['old']}" + (f"  ->  {a['new']}" if a['new'] else ''))
        if len(rows) > 12:
            print(f'  ... {len(rows) - 12} more {status}')
    for f in report['locked_skipped'][:10]:
        print(f'  [locked, skipped] {f}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--old-root', required=True, type=Path)
    parser.add_argument('--new-root', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='Rewrite references (default is a dry run)')
    parser.add_argument('--report', type=Path, help='Write the full JSON report here')
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--pid', type=int, help='Attach to this existing SOLIDWORKS PID')
    target.add_argument('--launch', action='store_true', help='Start one chat-owned instance and retire it afterwards')
    parser.add_argument('--session-file', help='With --launch: new absolute chat-owned session file')
    parser.add_argument('--wait-resources', type=int, default=30, help='With --launch: minutes to wait for the resource gate')
    parser.add_argument('--journal-warning-action', choices=('manual', 'dismiss'), default='manual',
                        help='With --launch: dismiss only that PID\'s journal/AutoRecover warning')
    args = parser.parse_args(argv)
    if args.launch and not args.session_file:
        parser.error('--launch requires --session-file')
    try:
        rr.validate_roots(args.old_root, args.new_root)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.new_root.is_dir():
        parser.error(f'--new-root does not exist: {args.new_root}')
    files = rr.native_files(args.new_root)
    held = None
    try:
        if args.launch:
            pid, held = launch(args.session_file, args.wait_resources, args.journal_warning_action)
        else:
            pid = args.pid
        app = connect(pid)
        report = rr.rebase(app, files, args.old_root, args.new_root, apply=args.apply)
        report['pid'] = pid
        report['launched_by_tool'] = bool(held)
        if args.report:
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        summarize(report)
        return 0 if report['verified'] in (None, True) else 1
    except (ValueError, RuntimeError) as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 2
    finally:
        if held is not None:
            try:
                if 'app' in locals():
                    retire(app, held)
            finally:
                held.Close()


if __name__ == '__main__':
    raise SystemExit(main())
