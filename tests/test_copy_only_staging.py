import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from types import SimpleNamespace
from solidworks_mcp.native_pack import NativePack

class CopyOnlyTests(unittest.TestCase):
    def test_root_copy_captures_memory_without_saving_clean_references(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);sources=[root/'a.sldasm',root/'b.sldprt',root/'c.stp']
            for p in sources:p.write_bytes(b'original')
            doc=SimpleNamespace(GetPathName=str(sources[0]),GetTitle='a',GetSaveFlag=False,SaveAs3=Mock())
            clean=SimpleNamespace(GetSaveFlag=False,SaveAs3=Mock())
            def save(path,version,flags):
                self.assertEqual(flags,3);Path(path).write_bytes(b'memory');return 0
            doc.SaveAs3.side_effect=save
            pack=object.__new__(NativePack);pack.doc=doc;pack.app=Mock();pack.extension=Mock()
            pack.app.GetOpenDocumentByName.side_effect=[doc,clean,None];pack.document_adapter=lambda d:d
            pack._sources=list(map(str,sources));pack._outputs=[str(root/'private'/p.name) for p in sources]
            self.assertEqual(pack.save(),[0,0,0])
            self.assertEqual(Path(pack._outputs[0]).read_bytes(),b'memory')
            self.assertEqual(Path(pack._outputs[1]).read_bytes(),b'original')
            self.assertTrue(all(p.read_bytes()==b'original' for p in sources))
            clean.SaveAs3.assert_not_called();pack.extension.SavePackAndGo.assert_not_called()

    def test_source_mutation_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'root.sldasm';source.write_bytes(b'original')
            doc=SimpleNamespace(GetPathName=str(source),GetTitle='root',GetSaveFlag=False,SaveAs3=Mock())
            def save(*args):source.write_bytes(b'changed');return 0
            doc.SaveAs3.side_effect=save
            pack=object.__new__(NativePack);pack.doc=doc;pack.app=Mock();pack.app.GetOpenDocumentByName.return_value=doc
            pack.document_adapter=lambda d:d;pack._sources=[str(source)];pack._outputs=[str(Path(folder)/'copy.sldasm')]
            with self.assertRaisesRegex(RuntimeError,'Source changed'):pack.save()

