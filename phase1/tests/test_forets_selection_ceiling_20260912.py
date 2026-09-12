import itertools
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_selection_ceiling_20260912 import pool_bounds


class CeilingTests(unittest.TestCase):
    def test_all_binary_validity_patterns_against_bound(self):
        for bits in itertools.product((False,True),repeat=4):
            rows=[dict(valid=b,score=float(i) if b else None,seconds=5.) for i,b in enumerate(bits)]
            for selected in itertools.combinations(range(4),2):
                value=pool_bounds(rows,selected,True)
                self.assertEqual(value['max_top2_valid'],min(2,sum(bits)))
                self.assertEqual(value['attained_feasibility_ceiling'],sum(bits[i] for i in selected)==min(2,sum(bits)))
    def test_quality_direction_and_zero_support(self):
        rows=[dict(valid=True,score=float(i),seconds=5.) for i in range(4)]
        self.assertEqual(pool_bounds(rows,[0,1],True)['quality_regret_to_bound'],0)
        self.assertEqual(pool_bounds(rows,[0,1],False)['quality_regret_to_bound'],2)
        rows=[dict(valid=False,score=None,seconds=5.) for _ in range(4)]
        self.assertIsNone(pool_bounds(rows,[0,1],True)['break_even_rank_seconds_intercept'])
    def test_break_even_identity(self):
        rows=[dict(valid=i<2,score=.5 if i<2 else None,seconds=float(i+1)) for i in range(4)]
        r=pool_bounds(rows,[0,1],True);g=20.
        rank=r['break_even_rank_seconds_G_coefficient']*g+r['break_even_rank_seconds_intercept']
        self.assertAlmostEqual((g+rank+r['mean_selected_program_seconds'])/r['selected_valid_probability'],
                               (g+r['mean_uniform_program_seconds'])/r['uniform_valid_probability'])


if __name__=='__main__':unittest.main()
