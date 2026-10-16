import unittest
from clock_contention_readout_20261016 import effects
class Readout(unittest.TestCase):
    def fixture(self):
        return [dict(program=p,mode=m,valid=True,steps=100 if m=='solo' else 70,
                     score=(.9 if m=='solo' else .8) if p==0 else (.02 if m=='solo' else .03))
                for p in (0,1) for m in ('solo','colocated') for _ in range(2)]
    def test_direction(self):
        for x in effects(self.fixture()):
            self.assertTrue(x['all_colocated_steps_lower']);self.assertTrue(x['all_colocated_scores_worse'])
            self.assertLess(x['oriented_mean_score_delta'],0)
    def test_missing_is_not_zero(self):
        r=self.fixture();r[0]['valid']=False
        self.assertFalse(effects(r)[0]['complete'])
    def test_repeat_noise_prevents_separation(self):
        r=self.fixture();r[0]['score']=.1;r[0]['steps']=10
        q=effects(r)[0];self.assertFalse(q['all_colocated_scores_worse']);self.assertFalse(q['all_colocated_steps_lower'])
if __name__=='__main__':unittest.main()
