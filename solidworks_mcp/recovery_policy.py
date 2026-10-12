"""Read recovery preferences from the bound CAD instance without changing them."""
import math,hashlib,os
from pathlib import Path

# SW2023 swconst.tlb: swAutoSaveEnable, swBackupEnable, swAutoSaveInterval,
# swAutoSaveIntervalMode; mode 2 is minutes, mode 1 is change count.
def automatic_policy(app, pid, environment):
    actual = app.GetProcessID
    actual = actual() if callable(actual) else actual
    if int(actual) != int(pid):
        raise RuntimeError('Recovery preference application PID mismatch')
    auto = bool(app.GetUserPreferenceToggle(319))
    backup = bool(app.GetUserPreferenceToggle(320))
    native = {'auto_recover_enabled':auto, 'backup_enabled':backup}
    if not auto and not backup:
        return {'enabled':False, 'source':'solidworks', 'preferences':native}
    minutes = int(app.GetUserPreferenceIntegerValue(3))
    mode = int(app.GetUserPreferenceIntegerValue(301))
    native.update(interval_value=minutes, interval_mode=mode)
    override = environment.get('SOLIDWORKS_RECOVERY_INTERVAL')
    if override is not None:
        seconds = float(override)
    elif auto:
        if mode != 2 or minutes <= 0:
            raise ValueError('AutoRecover interval is not a positive minute interval; configure SOLIDWORKS_RECOVERY_INTERVAL explicitly')
        seconds = minutes * 60.0
    else:
        # Native backup-only runs on save, not a timer. This timer supplements
        # it with unsaved recovery; it does not replace native backup copies.
        seconds = minutes * 60.0 if mode == 2 and minutes > 0 else 60.0
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('Recovery interval must be positive and finite')
    session = Path(environment.get('SOLIDWORKS_SESSION_FILE',''))
    if not session.is_absolute():
        raise ValueError('Automatic recovery requires an absolute owned session file')
    directory = environment.get('SOLIDWORKS_RECOVERY_DIRECTORY')
    if directory is None:
        local=Path(environment.get('LOCALAPPDATA') or os.environ.get('LOCALAPPDATA',''))
        if not local.is_absolute():raise ValueError('Automatic recovery requires an absolute LOCALAPPDATA directory')
        key=hashlib.sha256(str(session.resolve()).casefold().encode()).hexdigest()[:16]
        directory = str(local/'SWMCP'/key)
    settings = {'interval_seconds':seconds}
    for key, variable in [('assemblies','ASSEMBLIES'),('drawings','DRAWINGS'),
                          ('all_documents','ALL_DOCUMENTS'),('background_activation','BACKGROUND_ACTIVATION')]:
        settings[key] = environment.get('SOLIDWORKS_RECOVERY_'+variable,'1') == '1'
    return {'enabled':True,'source':'solidworks','preferences':native,
            'directory':directory,'settings':settings}
