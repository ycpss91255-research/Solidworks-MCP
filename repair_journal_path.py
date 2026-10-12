"""Inspect, or explicitly repair, the per-user journal path while CAD is closed."""
import argparse
import json
import os
from pathlib import Path
import re
import winreg

from launch_solidworks import launcher_lock
from solidworks_mcp.journal_registry import VALUE


def running_solidworks():
    # WMI enumerates process names without silently ignoring access-denied PIDs.
    # A failed inventory must propagate: it is not proof that CAD is absent.
    import pythoncom
    import win32com.client
    def query():
        # Release every WMI wrapper before uninitializing this COM apartment.
        service = win32com.client.GetObject('winmgmts:')
        return sorted(int(p.ProcessId) for p in service.ExecQuery(
            "SELECT ProcessId FROM Win32_Process WHERE Name='SLDWORKS.exe'"))
    pythoncom.CoInitialize()
    try:
        return query()
    finally:
        pythoncom.CoUninitialize()


def inspect(version):
    if not re.fullmatch(r'20\d{2}', version):
        raise ValueError('Expected a four-digit SolidWorks year')
    key_path = rf'Software\SolidWorks\SOLIDWORKS {version}\ExtReferences'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        original, value_type = winreg.QueryValueEx(key, VALUE)
    target = Path(os.environ['APPDATA']) / 'SOLIDWORKS' / f'SOLIDWORKS {version}'
    if not target.is_absolute():
        raise ValueError('APPDATA must be absolute')
    return {'key': key_path, 'value_name': VALUE, 'original': original,
            'value_type': value_type, 'assigned': str(target),
            'placeholder_present': 'CURRENT_USER' in Path(original).parts,
            'original_exists': Path(original).is_dir()}


def repair(plan, evidence, inventory=running_solidworks):
    evidence = Path(evidence)
    if not evidence.is_absolute():
        raise ValueError('Backup file must be absolute')
    if not plan['placeholder_present'] or plan['value_type'] not in (
            winreg.REG_SZ, winreg.REG_EXPAND_SZ):
        raise ValueError('Only the literal CURRENT_USER placeholder is repaired')
    with launcher_lock():
        pids = inventory()
        if pids:
            raise RuntimeError(f'SolidWorks still running: {pids}; registry unchanged')
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, plan['key'], 0,
                           winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            if winreg.QueryValueEx(key, VALUE) != (plan['original'], plan['value_type']):
                raise RuntimeError('Journal setting changed since inspection')
            # Reserve the backup exclusively, before any registry mutation.
            state = dict(plan, phase='prepared')
            with evidence.open('x', encoding='utf-8') as stream:
                json.dump(state, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            Path(plan['assigned']).mkdir(parents=True, exist_ok=True)
            pids = inventory()
            if pids:
                raise RuntimeError(f'SolidWorks started during preparation: {pids}; registry unchanged')
            if winreg.QueryValueEx(key, VALUE) != (plan['original'], plan['value_type']):
                raise RuntimeError('Journal setting changed during preparation')
            winreg.SetValueEx(key, VALUE, 0, plan['value_type'], plan['assigned'])
            if winreg.QueryValueEx(key, VALUE) != (plan['assigned'], plan['value_type']):
                raise RuntimeError('Journal setting readback mismatch; inspect backup before retrying')
            state['phase'] = 'applied'
            state['processes_after_write'] = inventory()
            temporary = evidence.with_name(evidence.name + '.tmp')
            with temporary.open('x', encoding='utf-8') as stream:
                json.dump(state, stream, indent=2)
            os.replace(temporary, evidence)
            return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='2023')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    if args.apply and args.backup is None:
        parser.error('--apply requires --backup with a new absolute file path')
    try:
        plan = inspect(args.version)
        result = repair(plan, args.backup) if args.apply else dict(
            plan, running_pids=running_solidworks(), phase='inspection_only')
        print(json.dumps(result, indent=2))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
