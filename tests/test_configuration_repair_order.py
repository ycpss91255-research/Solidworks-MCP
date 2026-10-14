import unittest
from pathlib import Path
from types import SimpleNamespace

from tests.configuration_repair_candidate import apply_candidate


class EquationManager:
    def __init__(self):
        self._oleobj_=self
        self.rows=['"D1@撐桿本體" = "驅動長度@支撐條-6.Part"',
                   '"D2@孔草圖" = "D1@撐桿本體"/2-"端距"',
                   '"聯動高度" = "驅動高度@支柱-1.Part"']
        self.events=[]
    def GetCount(self):return len(self.rows)
    def Equation(self,i):return self.rows[i]
    def Delete(self,i):self.events.append(('delete',i));self.rows.pop(i);return i
    def SetEquation(self,i,value):self.rows[i]=value
    def Add3(self,i,text,solve,scope,names):self.rows.append(text);return len(self.rows)-1


class Model:
    def __init__(self):
        self.eq=EquationManager();self.configs={'橫撐','斜撐'}
        self.ConfigurationManager=SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name='橫撐'))
        self._oleobj_=self;self.created_with_equations=None;self.mutations=[]
        self.Extension=SimpleNamespace(CustomPropertyManager=lambda name:SimpleNamespace(Add3=lambda *args:0))
    def GetPathName(self):return str(Path('C:/private-fixture/支撐條.SLDPRT'))
    def GetTitle(self):return '支撐條.SLDPRT'
    def GetEquationMgr(self):return self.eq
    def GetConfigurationByName(self,name):return name if name in self.configs else None
    def DeleteConfiguration2(self,name):self.mutations.append('delete-config');self.configs.remove(name);return True
    def AddConfiguration3(self,name,comment,alternate,options):
        self.created_with_equations=list(self.eq.rows)
        self.mutations.append('create-config');self.configs.add(name)
        assert options==128
        return object()


class RepairOrderingTests(unittest.TestCase):
    def setUp(self):
        self.doc=Model()
        self.app=SimpleNamespace(GetProcessID=lambda:123,GetDocuments=lambda:[self.doc],
            GetOpenDocumentByName=lambda name:self.doc,ActivateDoc3=lambda *args:(True,0))
        self.types=SimpleNamespace(IModelDoc2=lambda x:x,IEquationMgr=lambda x:x)
        self.args=(self.app,self.types,Path('C:/private-fixture'),123,
                   {'驅動長度':{'type':30,'get6':[2,'1332.097557']}})

    def test_working_equations_retained_until_inactive_configuration_exists(self):
        result=apply_candidate(*self.args)
        equations=self.doc.created_with_equations
        self.assertTrue(equations)
        self.assertTrue(any('D1@撐桿本體' in text for text in equations))
        self.assertFalse(any('聯動' in text for text in equations))
        self.assertFalse(any('@支撐條-6.Part' in text for text in equations))
        self.assertFalse(result['saved'])
        self.assertFalse(result['geometry_verified'])
        self.assertEqual(self.doc.ConfigurationManager.ActiveConfiguration.Name,'橫撐')

    def test_wrong_pid_rejected_before_mutation(self):
        self.app.GetProcessID=lambda:999
        with self.assertRaises(AssertionError):apply_candidate(*self.args)
        self.assertEqual(self.doc.mutations,[])

    def test_nonprivate_loaded_document_rejected_before_mutation(self):
        foreign=SimpleNamespace(_oleobj_=SimpleNamespace(GetPathName=lambda:'C:/working/formal.SLDPRT'))
        self.app.GetDocuments=lambda:[self.doc,foreign]
        with self.assertRaises(AssertionError):apply_candidate(*self.args)
        self.assertEqual(self.doc.mutations,[])
