import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from solidworks_mcp.native_pack import NativePack

class PackNameTests(unittest.TestCase):
    def pack(self,sources):
        p=object.__new__(NativePack);p.pack=Mock()
        p.pack.GetDocumentNames.return_value=(sources,True)
        def folder(override,target):
            p.target=Path(target);return True
        def names():
            outputs=[str(p.target/Path(source).parent.name/(p.pack.AddPrefix+Path(source).name)) for source in sources]
            return outputs,[0]*len(outputs),True
        p.pack.SetSaveToName.side_effect=folder
        p.pack.GetDocumentSaveToNames.side_effect=names
        alias=patch('win32api.GetShortPathName',side_effect=lambda path:path);alias.start();self.addCleanup(alias.stop)
        return p
    def test_same_basename_gets_distinct_private_names_in_source_order(self):
        p=self.pack(['C:/one/sensor.SLDPRT','C:/two/SENSOR.sldprt','C:/assembly.SLDASM'])
        outputs=p.destinations('C:/private','r123-')
        self.assertEqual(len(set(v.casefold() for v in outputs)),3)
        self.assertTrue(all(Path(v).is_relative_to(Path('C:/private')) for v in outputs))
        self.assertEqual([Path(v).name for v in outputs],['r-sensor.SLDPRT','r-SENSOR.sldprt','r-assembly.SLDASM'])
        p.pack.SetSaveToName.assert_called_once_with(True,'C:/private')
        self.assertFalse(p.pack.FlattenToSingleFolder)
        p.pack.SetDocumentSaveToNames.assert_not_called()
    def test_step_source_extension_is_preserved(self):
        p=self.pack(['C:/part.SLDPRT','C:/external.stp'])
        self.assertEqual(Path(p.destinations('C:/private','r-')[1]).suffix,'.stp')
    def test_native_name_assignment_failure_is_not_success(self):
        p=self.pack(['C:/part.SLDPRT']);p.pack.SetSaveToName.side_effect=None;p.pack.SetSaveToName.return_value=False
        with self.assertRaisesRegex(RuntimeError,'package directory'):p.destinations('C:/private','r-')
    def test_native_destination_escape_is_rejected(self):
        p=self.pack(['C:/one.SLDPRT','C:/two.SLDPRT'])
        p.pack.GetDocumentSaveToNames.side_effect=lambda:(['C:/original/one.SLDPRT','C:/private/two.SLDPRT'],[0,0],True)
        with self.assertRaisesRegex(RuntimeError,'escape'):p.destinations('C:/private','r-')
    def test_native_long_destination_is_rejected_before_save(self):
        p=self.pack(['C:/part.SLDPRT'])
        p.pack.GetDocumentSaveToNames.side_effect=lambda:(['C:/private/'+('x'*250)+'.SLDPRT'],[0],True)
        with self.assertRaisesRegex(RuntimeError,'259-character'):p.destinations('C:/private','r-')
        p.pack.SetDocumentSaveToNames.assert_not_called()

if __name__=='__main__':unittest.main()
