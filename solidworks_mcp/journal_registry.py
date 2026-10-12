"""Experimental reversible journal-folder lease; not enabled by the launcher.

The caller must hold the launch lock until the new process has opened its own
journal. This changes a per-user setting briefly, not a per-process registry
view. Real CAD behavior and other settings must be verified before integration.
"""
import json
from pathlib import Path
import winreg

VALUE = 'SolidWorks Journal Folders'


class JournalFolderLease:
    def __init__(self, key_path, folder, evidence):
        self.key_path = key_path
        self.folder = Path(folder)
        self.evidence = Path(evidence)
        if not self.folder.is_absolute() or not self.evidence.is_absolute():
            raise ValueError('Folder and evidence paths must be absolute')
        self.key = None
        self.original = None
        self.value_type = None
        self.state = None

    def _record(self, phase):
        self.state['phase'] = phase
        self.evidence.write_text(json.dumps(self.state, indent=2), encoding='utf-8')

    def __enter__(self):
        if self.evidence.exists():
            raise RuntimeError('Existing journal lease evidence requires inspection first')
        self.folder.mkdir(parents=True, exist_ok=True)
        self.evidence.parent.mkdir(parents=True, exist_ok=True)
        self.key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path, 0,
                                  winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE)
        assigned = False
        try:
            self.original, self.value_type = winreg.QueryValueEx(self.key, VALUE)
            if self.value_type not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                raise ValueError('Journal folder registry value must be a string')
            self.state = {'key':self.key_path, 'value_name':VALUE,
                          'original':self.original, 'value_type':self.value_type,
                          'assigned':str(self.folder)}
            self._record('prepared')  # Backup must exist before modifying the value.
            winreg.SetValueEx(self.key, VALUE, 0, self.value_type, str(self.folder))
            assigned = True
            self._record('assigned')
            return self
        except BaseException:
            try:
                if assigned:
                    self.restore()
            finally:
                self.key.Close()
                self.key = None
            raise

    def restore(self):
        current, value_type = winreg.QueryValueEx(self.key, VALUE)
        if (current, value_type) != (str(self.folder), self.value_type):
            self._record('conflict')
            raise RuntimeError('Journal folder was changed externally; refusing to overwrite it')
        winreg.SetValueEx(self.key, VALUE, 0, self.value_type, self.original)
        self._record('restored')

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.restore()
        finally:
            self.key.Close()
            self.key = None
        return False
