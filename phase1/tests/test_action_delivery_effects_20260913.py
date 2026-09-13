import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_action_prospective_20260913 import paired_effects

class EffectsTests(unittest.TestCase):
    def rows(self):
        return [dict(task=t,seed=s,technical_eligible=True,primary_valid=True,action_valid=True,
            quality_comparable=True,action_oriented_gain=0.)
            for t in ('leaf-classification','spaceship-titanic') for s in (34,35,36,37)]
    def test_ties_no_automatic_gain(self):
        groups=paired_effects(self.rows())
        self.assertTrue(all(g['ties']==4 and g['wins']==0 and g['median_gain']==0 for g in groups))
    def test_missing_not_zero_and_negative_retained(self):
        rows=self.rows();rows[0].update(primary_valid=False,quality_comparable=False,action_oriented_gain=None)
        rows[1]['action_oriented_gain']=-.2;rows[2]['action_oriented_gain']=.1
        g=paired_effects(rows)[0]
        self.assertEqual(g['quality_comparable'],3);self.assertEqual(g['losses'],1);self.assertEqual(g['wins'],1)
        self.assertEqual(g['primary_missing_action_valid'],1)
    def test_duplicate_or_selected_subset_rejected(self):
        rows=self.rows()
        with self.assertRaises(ValueError):paired_effects(rows[:-1])
        rows[-1]=copy.deepcopy(rows[0])
        with self.assertRaises(ValueError):paired_effects(rows)

if __name__=='__main__':unittest.main()
