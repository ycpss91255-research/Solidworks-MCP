import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from solidworks_mcp.utils.sw_finder import SolidWorksFinder

class LocalizedTemplateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for name,value in [('TEMPLATE_SUBDIRS',[]),('PROGRAMDATA_TEMPLATE_PATHS',[str(self.root)])]:
            p=patch.object(SolidWorksFinder,name,value);p.start();self.addCleanup(p.stop)
    def find(self,kind):return SolidWorksFinder.find_template(kind,str(self.root/'SLDWORKS.exe'))
    def test_localized_template_of_each_type_is_found(self):
        for kind,filename in [('part','零件.PRTDOT'),('assembly','組合件.ASMDOT'),('drawing','工程圖.DRWDOT')]:
            path=self.root/filename;path.touch()
            self.assertEqual(self.find(kind),str(path))
    def test_multiple_custom_templates_are_not_arbitrarily_selected(self):
        (self.root/'甲.PRTDOT').touch();(self.root/'乙.PRTDOT').touch()
        self.assertIsNone(self.find('part'))
    def test_existing_standard_template_keeps_precedence(self):
        (self.root/'零件.PRTDOT').touch();preferred=self.root/'Part.prtdot';preferred.touch()
        self.assertEqual(self.find('part'),str(preferred))

if __name__=='__main__':unittest.main()
