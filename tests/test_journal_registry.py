"""Native registry tests use only a disposable test key, never CAD settings."""
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import winreg

from solidworks_mcp.journal_registry import JournalFolderLease, VALUE


class JournalLeaseTests(unittest.TestCase):
    def setUp(self):
        self.path = r'Software\SolidWorksMCPTests' + '\\' + uuid.uuid4().hex
        self.key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.path, 0, winreg.KEY_ALL_ACCESS)
        winreg.SetValueEx(self.key, VALUE, 0, winreg.REG_SZ, 'original-test-folder')
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)/'journal'
        self.evidence = Path(self.temp.name)/'lease.json'

    def tearDown(self):
        self.key.Close()
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, self.path)
        self.temp.cleanup()

    def lease(self):
        return JournalFolderLease(self.path, self.folder, self.evidence)

    def test_assign_and_restore_with_backup(self):
        with self.lease():
            self.assertEqual(winreg.QueryValueEx(self.key, VALUE)[0], str(self.folder))
            self.assertEqual(json.loads(self.evidence.read_text())['original'], 'original-test-folder')
        self.assertEqual(winreg.QueryValueEx(self.key, VALUE)[0], 'original-test-folder')
        self.assertEqual(json.loads(self.evidence.read_text())['phase'], 'restored')

    def test_exception_restores_setting(self):
        with self.assertRaisesRegex(RuntimeError, 'startup failed'):
            with self.lease():
                raise RuntimeError('startup failed')
        self.assertEqual(winreg.QueryValueEx(self.key, VALUE)[0], 'original-test-folder')

    def test_external_update_is_preserved(self):
        with self.assertRaisesRegex(RuntimeError, 'changed externally'):
            with self.lease():
                winreg.SetValueEx(self.key, VALUE, 0, winreg.REG_SZ, 'external-setting')
        self.assertEqual(winreg.QueryValueEx(self.key, VALUE)[0], 'external-setting')
        self.assertEqual(json.loads(self.evidence.read_text())['phase'], 'conflict')

    def test_existing_evidence_blocks_a_new_lease(self):
        self.evidence.write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'requires inspection'):
            with self.lease():
                pass
        self.assertEqual(winreg.QueryValueEx(self.key, VALUE)[0], 'original-test-folder')
