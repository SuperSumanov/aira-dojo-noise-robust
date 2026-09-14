import unittest
from summarize_closed_evidence_20260914 import opportunity,ARMS

def row(labels,choices=None):return dict(labels=labels,choices=choices or dict.fromkeys(ARMS,0))
class TestOpportunity(unittest.TestCase):
    def test_partition(self):
        out=opportunity([row([False,False]),row([False,True]),row([True,True]),row([None,True])])
        self.assertEqual([out[k] for k in ('both_invalid','mixed_validity','both_valid','unknown')],[1,1,1,1])
        self.assertEqual(out['any_valid_known_pools'],2)
        self.assertEqual(out['selected_valid_by_policy'],dict.fromkeys(ARMS,1))
        self.assertEqual(out['valid_opportunities_missed_by_all'],1)
    def test_different_choices(self):
        out=opportunity([row([False,True],dict(uniform=0,short_code=1,learned_validity=0,class_gate=1))])
        self.assertEqual(out['valid_opportunities_missed_by_all'],0)
        self.assertEqual(out['selected_valid_by_policy']['short_code'],1)
    def test_unknown_not_failure(self):
        out=opportunity([row([None,False])])
        self.assertEqual(out['unknown'],1);self.assertEqual(out['known_pools'],0)
        self.assertEqual(out['both_invalid'],0)
    def test_integer_labels_rejected(self):
        with self.assertRaises(ValueError):opportunity([row([0,1])])
    def test_invalid_choice_rejected(self):
        with self.assertRaises(ValueError):opportunity([row([False,True],dict.fromkeys(ARMS,True))])
if __name__=='__main__':unittest.main()
