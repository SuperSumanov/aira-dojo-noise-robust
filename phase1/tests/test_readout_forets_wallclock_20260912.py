import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_forets_wallclock_20260912 import effects,TASKS,ARMS


class EffectsTests(unittest.TestCase):
    def rows(self):
        return [dict(task=t,seed=s,arm=a,valid=True,score=.5 if a==ARMS[0] else .4,
                     technical_eligible=True,api_cost_usd=.01)
                for t in TASKS for s in (22,23) for a in ARMS]
    def test_direction_and_across_seed_dispersion(self):
        result=effects(self.rows())
        self.assertAlmostEqual(result['pairs'][0]['critic_oriented_score_gain'],.1)
        self.assertAlmostEqual(result['pairs'][2]['critic_oriented_score_gain'],-.1)
        self.assertEqual(result['gain_summary'][0]['sample_std_gain'],0)
    def test_missing_not_imputed_and_infrastructure_separate(self):
        rows=self.rows();rows[0].update(valid=False,score=None,technical_eligible=False)
        result=effects(rows)
        self.assertIsNone(result['pairs'][0]['critic_oriented_score_gain'])
        self.assertFalse(result['pairs'][0]['both_technically_eligible'])
        self.assertIsNone(result['gain_summary'][0]['sample_std_gain'])
        rows[0]['score']=0
        with self.assertRaises(ValueError):effects(rows)
    def test_full_matrix_no_dedup_or_selection(self):
        with self.assertRaises(ValueError):effects(self.rows()[:-1])
        rows=self.rows();rows[-1]=copy.deepcopy(rows[0])
        with self.assertRaises(ValueError):effects(rows)
    def test_explicit_successor_seed_pair(self):
        rows=self.rows()
        for r in rows:r['seed']+=2
        self.assertEqual(len(effects(rows,seeds=(24,25))['pairs']),4)
        with self.assertRaises(ValueError):effects(rows)
        with self.assertRaises(ValueError):effects(rows,seeds=(24,24))
    def test_single_vote_complete_seeds(self):
        rows=self.rows()
        for r in rows:r['seed']+=4
        self.assertEqual(len(effects(rows,seeds=(26,27))['pairs']),4)
        with self.assertRaises(ValueError):effects(rows[:-1],seeds=(26,27))


if __name__=='__main__':unittest.main()
