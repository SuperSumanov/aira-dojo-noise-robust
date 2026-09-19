import unittest
from analyze_comparison_frozen_reward_20260919 import pool_metrics

def rows():return [dict(slot=i,node=str(i),valid=i<2,score=.1+i if i<2 else None,reward=6.-i) for i in range(6)]
class RewardPoolAnalysis(unittest.TestCase):
    def test_good_and_bad_frozen_rank_with_exact_uniform(self):
        data=rows();p=pool_metrics(data)
        self.assertEqual(p['policies']['uniform_two_of_six']['probability_any_valid'],.6)
        self.assertEqual(p['policies']['frozen_top_two']['probability_any_valid'],1.)
        self.assertGreater(p['policies']['frozen_top_two']['net_preference_vs_uniform'],0)
        for r in data:r['reward']=-r['reward']
        bad=pool_metrics(data);self.assertEqual(bad['policies']['frozen_top_two']['probability_any_valid'],0)
        self.assertLess(bad['policies']['frozen_top_two']['net_preference_vs_uniform'],0)
    def test_all_failed_remains_a_complete_tied_pool(self):
        data=rows()
        for r in data:r.update(valid=False,score=None)
        p=pool_metrics(data);self.assertIsNone(p['validity_ranking_auc'])
        self.assertTrue(all(v['probability_any_valid']==v['net_preference_vs_uniform']==0 for v in p['policies'].values()))
    def test_ties_do_not_use_labels(self):
        data=rows()
        for r in data:r['reward']=0.
        self.assertEqual(pool_metrics(list(reversed(data)))['critic_order'],list(range(6)))
    def test_unknown_not_dropped(self):
        data=rows();data[0]['valid']=None
        with self.assertRaises(ValueError):pool_metrics(data)

if __name__=='__main__':unittest.main()
