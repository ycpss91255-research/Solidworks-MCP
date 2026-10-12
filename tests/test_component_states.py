import unittest
from unittest.mock import Mock
from solidworks_mcp.component_states import restore_suppression,occurrence_key,missing_reference_inventory

class ComponentStateTests(unittest.TestCase):
    def row(self,suppressed=False,path='C:/private/part.SLDPRT',x=0):
        matrix=[0.0]*16;matrix[0]=matrix[4]=matrix[8]=matrix[12]=1;matrix[9]=x
        return {'source_path':path,'matrix':matrix,'suppressed':suppressed}
    def restore(self,current,desired,write=None):
        def set_state(row,target):row['suppressed']=target
        return restore_suppression(current,desired,lambda row:dict(row),write or set_state)
    def test_restores_suppression_without_changing_placement(self):
        row=self.row();desired=self.row(True)
        result=self.restore([row],[desired])
        self.assertEqual(row,desired);self.assertEqual(result['changed_occurrences'],1)
    def test_signed_zero_is_same_numeric_transform(self):
        first=self.row();second=self.row();second['matrix'][3]=-0.0
        self.assertEqual(occurrence_key(first),occurrence_key(second))
    def test_missing_or_moved_occurrence_cannot_mutate(self):
        write=Mock()
        for current in ([],[self.row(x=0.1)]):
            with self.assertRaisesRegex(ValueError,'placements'):self.restore(current,[self.row(True)],write)
        write.assert_not_called()
    def test_coincident_ambiguous_states_cannot_mutate(self):
        write=Mock()
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            self.restore([self.row(),self.row()],[self.row(True),self.row(False)],write)
        write.assert_not_called()
    def test_failed_setter_is_not_success(self):
        with self.assertRaisesRegex(RuntimeError,'not applied'):
            self.restore([self.row()],[self.row(True)],Mock())
    def test_nonfinite_transform_is_rejected(self):
        row=self.row();row['matrix'][0]=float('nan')
        with self.assertRaisesRegex(ValueError,'finite'):occurrence_key(row)
    def test_missing_reference_inventory_keeps_active_and_suppressed_instances(self):
        result=missing_reference_inventory([self.row(False),self.row(True)],exists=lambda path:False)
        self.assertEqual(result['c:/private/part.sldprt'],{'active':1,'suppressed':1})
    def test_existing_reference_is_not_marked_missing(self):
        self.assertEqual(missing_reference_inventory([self.row()],exists=lambda path:True),{})
    def test_shared_subassembly_change_is_rechecked(self):
        current=[self.row(),self.row()];desired=[self.row(True),self.row(True)];calls=[]
        def change(row,target):
            calls.append(row)
            for other in current:other['suppressed']=target
        result=self.restore(current,desired,change)
        self.assertEqual(len(calls),1);self.assertEqual(result['verified_occurrences'],2)

if __name__=='__main__':unittest.main()
