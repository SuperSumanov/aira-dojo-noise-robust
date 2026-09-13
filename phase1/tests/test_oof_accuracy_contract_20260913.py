from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from oof_accuracy_contract_20260913 import OOFAccuracy


class OOFTests(unittest.TestCase):
    def test_order_invariant(self):
        a=OOFAccuracy([0,0,1,1]);a.add([2,3],[1,1]);a.add([0,1],[0,0])
        self.assertEqual(a.score(),1.);self.assertEqual(a.marker(),'FINAL_VALIDATION_SCORE: 1.0')
    def test_incomplete_not_zero(self):
        a=OOFAccuracy([0,1]);a.add([0],[0])
        with self.assertRaises(ValueError):a.score()
    def test_duplicate_is_atomic(self):
        a=OOFAccuracy([0,1]);a.add([0],[0])
        with self.assertRaises(ValueError):a.add([1,0],[1,0])
        self.assertEqual(a.values,{0:0})
    def test_bad_ids_and_probabilities_rejected(self):
        for ids,preds in [([2],[1]),([.5],[1]),([True],[1]),([0],[.8]),([0,1],[0])]:
            with self.assertRaises(ValueError):OOFAccuracy([0,1]).add(ids,preds)
    def test_legitimate_zero_score(self):
        a=OOFAccuracy([0,1]);a.add([1,0],[0,1]);self.assertEqual(a.score(),0.)


if __name__=='__main__':unittest.main()
