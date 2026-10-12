"""Native registry checks use a disposable key, never the SolidWorks profile."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import winreg

import repair_journal_path as repair
from solidworks_mcp.journal_registry import VALUE


class JournalRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.key_path = 'Software\\SolidWorksMCPTests\\' + uuid.uuid4().hex
        self.key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.key_path,
                                     0, winreg.KEY_ALL_ACCESS)
        self.original = r'C:\Users\CURRENT_USER\AppData\Roaming\SolidWorks\SOLIDWORKS 2023'
        winreg.SetValueEx(self.key, VALUE, 0, winreg.REG_SZ, self.original)
        self.plan = {'key': self.key_path, 'value_name': VALUE,
                     'original': self.original, 'value_type': winreg.REG_SZ,
                     'assigned': str(self.folder/'journal'), 'placeholder_present': True}
        self.backup = self.folder/'backup.json'

    def tearDown(self):
        self.key.Close()
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.key_path)
        self.temp.cleanup()

    def value(self):
        return winreg.QueryValueEx(self.key, VALUE)[0]

    def test_live_cad_prevents_all_writes(self):
        with self.assertRaisesRegex(RuntimeError, 'still running'):
            repair.repair(self.plan, self.backup, lambda: [9336])
        self.assertEqual(self.value(), self.original)
        self.assertFalse(self.backup.exists())
        self.assertFalse(Path(self.plan['assigned']).exists())

    def test_success_backups_original_and_verifies_value(self):
        result = repair.repair(self.plan, self.backup, lambda: [])
        self.assertEqual(result['phase'], 'applied')
        self.assertEqual(self.value(), self.plan['assigned'])
        self.assertEqual(json.loads(self.backup.read_text())['original'], self.original)

    def test_new_process_during_preparation_keeps_registry(self):
        states = iter([[], [12616]])
        with self.assertRaisesRegex(RuntimeError, 'during preparation'):
            repair.repair(self.plan, self.backup, lambda: next(states))
        self.assertEqual(self.value(), self.original)
        self.assertEqual(json.loads(self.backup.read_text())['phase'], 'prepared')

    def test_existing_backup_is_not_overwritten(self):
        self.backup.write_text('old evidence')
        with self.assertRaises(FileExistsError):
            repair.repair(self.plan, self.backup, lambda: [])
        self.assertEqual(self.value(), self.original)
        self.assertEqual(self.backup.read_text(), 'old evidence')

    def test_external_setting_change_is_preserved(self):
        winreg.SetValueEx(self.key, VALUE, 0, winreg.REG_SZ, 'external')
        with self.assertRaisesRegex(RuntimeError, 'changed since inspection'):
            repair.repair(self.plan, self.backup, lambda: [])
        self.assertEqual(self.value(), 'external')

    def test_failed_inventory_does_not_mean_no_cad(self):
        with self.assertRaisesRegex(RuntimeError, 'inventory failed'):
            repair.repair(self.plan, self.backup,
                          lambda: (_ for _ in ()).throw(RuntimeError('inventory failed')))
        self.assertEqual(self.value(), self.original)
        self.assertFalse(self.backup.exists())

    def test_failed_backup_prevents_registry_mutation(self):
        with patch('repair_journal_path.os.fsync', side_effect=OSError('backup failure')):
            with self.assertRaises(OSError):
                repair.repair(self.plan, self.backup, lambda: [])
        self.assertEqual(self.value(), self.original)


if __name__ == '__main__':
    unittest.main()
