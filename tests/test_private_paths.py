from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from solidworks_mcp.private_paths import canonical_outputs

class PrivatePathTests(unittest.TestCase):
    def test_cached_parents_match_full_resolution_for_missing_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[Path(temp)/'nested'/'future'/f'part-{i}.SLDPRT' for i in range(20)]
            expected=[p.resolve() for p in paths]
            self.assertEqual(canonical_outputs(paths),expected)
            original=Path.resolve
            with patch.object(Path,'resolve',autospec=True,side_effect=original) as resolve:
                self.assertEqual(canonical_outputs(paths),expected)
                self.assertEqual(resolve.call_count,1)
    def test_parent_traversal_retains_actual_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'..'/'outside'/'part.SLDPRT'
            self.assertEqual(canonical_outputs([path]),[path.resolve()])

if __name__=='__main__':unittest.main()
