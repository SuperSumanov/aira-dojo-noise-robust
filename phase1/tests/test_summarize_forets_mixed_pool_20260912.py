import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from summarize_forets_mixed_pool_20260912 import subset

class PoolTests(unittest.TestCase):
    def test_missing_is_not_zero(self):
        rows=[dict(valid='False',score=''),dict(valid='True',score='.4')]
        self.assertEqual(subset(rows,[0,1]),dict(valid=1,total=2,valid_probability=.5,conditional_mean_score=.4))
        self.assertIsNone(subset(rows,[0])['conditional_mean_score'])
    def test_duplicate_and_out_of_range_rejected(self):
        rows=[dict(valid='True',score='.4')]
        for slots in ([0,0],[1],[-1]):
            with self.assertRaises(ValueError):subset(rows,slots)
    def test_pool_relative_slots(self):
        rows=[dict(valid='False',score=''),dict(valid='True',score='.2'),dict(valid='True',score='.6'),dict(valid='True',score='.1')]
        self.assertEqual(subset(rows,[1,2])['conditional_mean_score'],.4)
        self.assertEqual(subset(rows,[1,2])['valid_probability'],1.)

if __name__=='__main__':unittest.main()
