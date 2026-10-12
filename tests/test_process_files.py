import os
from pathlib import Path
import tempfile
import unittest
from solidworks_mcp.process_files import journal_handles


class JournalHandleTests(unittest.TestCase):
    def test_native_journal_owner_and_handle_closure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = (Path(folder) / 'swxJRNL.swj').resolve()
            with path.open('wb'):
                rows = journal_handles([os.getpid()])
                self.assertIn({'pid':os.getpid(), 'path':str(path)}, rows)
            rows = journal_handles([os.getpid()])
            self.assertNotIn({'pid':os.getpid(), 'path':str(path)}, rows)
