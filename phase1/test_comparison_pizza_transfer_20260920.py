import itertools,random,unittest
from comparison_auc_20260920 import rank_auc
from readout_comparison_pizza_transfer_20260920 import analyze
from run_comparison_pizza_transfer_20260920 import score_one

class Transfer(unittest.TestCase):
    def test_auc_matches_pairwise_definition(self):
        rng=random.Random(20260920)
        for _ in range(100):
            labels=[0,1]+[rng.randrange(2) for _ in range(8)];scores=[rng.randrange(4) for _ in labels]
            pairs=[(scores[i]>scores[j])+.5*(scores[i]==scores[j]) for i,y in enumerate(labels) if y==1 for j,z in enumerate(labels) if z==0]
            self.assertAlmostEqual(rank_auc(labels,scores),sum(pairs)/len(pairs))
    def test_orientation_high_auc(self):
        rows=[dict(slot=i,node=str(i),reward=6.-i,valid=True,score=1.-i/10) for i in range(6)]
        out=analyze(rows)['policies']['frozen_top_two'];self.assertEqual((out['wins'],out['ties'],out['losses']),(10,5,0))
        rows[0]['score']=0.;rows[1]['score']=.1
        out=analyze(rows)['policies']['frozen_top_two'];self.assertEqual((out['wins'],out['ties'],out['losses']),(0,1,14))
    def test_unknown_and_all_failure(self):
        rows=[dict(slot=i,node=str(i),reward=6.-i,valid=False,score=None) for i in range(6)]
        self.assertEqual(analyze(rows)['policies']['frozen_top_two']['ties'],15)
        rows[0]['valid']=None;self.assertEqual(analyze(rows)['status'],'UNKNOWN_NO_EFFECT_CLAIM')
    def test_exact_model_interface(self):
        class Scorer:
            def score_batch(self,pairs):
                assert pairs==[('task','full code')];return [.25]
        self.assertEqual(score_one(Scorer(),'task','full code'),.25)

if __name__=='__main__':unittest.main()
