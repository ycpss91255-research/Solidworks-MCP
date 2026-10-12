"""Preload directory guards execute before any process-memory access."""
import tempfile,unittest
from pathlib import Path
from solidworks_mcp.journal_preload_bootstrap import preload_created

class PreloadGuardTests(unittest.TestCase):
    def test_existing_private_journal_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            dll=root/'fixture.dll';dll.write_bytes(b'not executed')
            source=root/'source';source.mkdir()
            private=root/'private';private.mkdir()
            journal=private/'swxJRNL.swj';journal.write_text('preserved')
            with self.assertRaises(FileExistsError):
                preload_created(0,123,dll,source,private)
            self.assertEqual(journal.read_text(),'preserved')

    def test_shared_source_is_rejected_before_seed_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            dll=root/'fixture.dll';dll.write_bytes(b'not executed')
            source=root/'source';source.mkdir()
            with self.assertRaisesRegex(ValueError,'Invalid private paths'):
                preload_created(0,123,dll,source,source)
            self.assertFalse((source/'swxJRNL.swj').exists())
