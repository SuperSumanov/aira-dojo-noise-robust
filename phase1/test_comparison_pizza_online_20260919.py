import itertools,unittest
from readout_comparison_pizza_online_20260919 import rank_auc
from readout_comparison_online_continuation_20260919 import compare

class PizzaReadout(unittest.TestCase):
    def test_perfect_inverse_and_ties(self):
        self.assertEqual(rank_auc([0,1],[.1,.9]),1)
        self.assertEqual(rank_auc([1,0],[.1,.9]),0)
        self.assertEqual(rank_auc([0,1,1],[.5,.5,.5]),.5)
    def test_matches_pairwise_definition_exhaustively(self):
        for y in itertools.product((0,1),repeat=4):
            if not 0<sum(y)<4:continue
            for p in itertools.product((.1,.5,.9),repeat=4):
                pairs=[(p[i],p[j]) for i in range(4) for j in range(4) if y[i]==1 and y[j]==0]
                direct=sum((a>b)+.5*(a==b) for a,b in pairs)/len(pairs)
                self.assertAlmostEqual(rank_auc(list(y),list(p)),direct)
    def test_invalid_fails(self):
        for y,p in (([],[]),([1],[.5]),([0,2],[.1,.9]),([0,1],[float('nan'),.5])):
            with self.assertRaises(ValueError):rank_auc(y,p)
    def test_higher_is_better_difference(self):
        rows=[dict(index=i,seed=i//2+1,cache=i%2==i//2,valid_accepted_submission=True,score=.8 if i%2==i//2 else .7,accepted_seconds=20) for i in range(4)]
        groups=compare(rows,'auc_delta_cache_minus_baseline')['groups']
        self.assertTrue(all(g['auc_delta_cache_minus_baseline']>0 for g in groups))

if __name__=='__main__':unittest.main()
