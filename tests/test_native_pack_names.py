import unittest
from pathlib import Path
from unittest.mock import Mock
from solidworks_mcp.native_pack import NativePack

class PackNameTests(unittest.TestCase):
    def pack(self,sources):
        p=object.__new__(NativePack);p.pack=Mock()
        p.pack.GetDocumentNames.return_value=(sources,True)
        p.pack.SetDocumentSaveToNames.side_effect=lambda values:setattr(p,'outputs',list(values.value)) or True
        p.pack.GetDocumentSaveToNames.side_effect=lambda:(p.outputs,[0]*len(p.outputs),True)
        return p
    def test_same_basename_gets_distinct_private_names_in_source_order(self):
        p=self.pack(['C:/one/sensor.SLDPRT','C:/two/SENSOR.sldprt','C:/assembly.SLDASM'])
        outputs=p.destinations('C:/private','r123-')
        self.assertEqual(len(set(v.casefold() for v in outputs)),3)
        self.assertTrue(all(Path(v).parent==Path('C:/private') for v in outputs))
        self.assertTrue(all(Path(v).name.startswith('r123-') for v in outputs))
        p.pack.SetSaveToName.assert_called_once_with(False,'')
        from comtypes.automation import VT_ARRAY,VT_BSTR
        self.assertEqual(p.pack.SetDocumentSaveToNames.call_args.args[0].vt,VT_ARRAY|VT_BSTR)
    def test_step_source_extension_is_preserved(self):
        p=self.pack(['C:/part.SLDPRT','C:/external.stp'])
        self.assertEqual(Path(p.destinations('C:/private','r-')[1]).suffix,'.stp')
    def test_native_name_assignment_failure_is_not_success(self):
        p=self.pack(['C:/part.SLDPRT']);p.pack.SetDocumentSaveToNames.side_effect=None;p.pack.SetDocumentSaveToNames.return_value=False
        with self.assertRaisesRegex(RuntimeError,'per-document'):p.destinations('C:/private','r-')
    def test_native_reordering_or_override_is_rejected(self):
        p=self.pack(['C:/one.SLDPRT','C:/two.SLDPRT'])
        p.pack.GetDocumentSaveToNames.side_effect=lambda:(list(reversed(p.outputs)),[0,0],True)
        with self.assertRaisesRegex(RuntimeError,'retain'):p.destinations('C:/private','r-')

if __name__=='__main__':unittest.main()
