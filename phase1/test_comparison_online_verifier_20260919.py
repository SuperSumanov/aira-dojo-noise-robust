import copy,unittest
from verify_comparison_online_results_20260919 import verify
from test_comparison_online_readout_20260919 import fixture
from readout_comparison_online_continuation_20260919 import compare

def make():
    rows=fixture()
    for r in rows:r.update(lane=r['index']%2,budget_seconds=2100,independent_score=None)
    return dict(role='live_conditioned_rescue_not_full_e2e',allocation=dict(gpus=6,seconds=600,gpu_hours=1),rows=rows,comparison=compare(rows))

class VerifierTests(unittest.TestCase):
    def test_all_fail(self):self.assertEqual(verify(make())['validity_ties'],2)
    def test_single_success_has_no_significance(self):
        d=make();d['rows'][0].update(valid_accepted_submission=True,score=.4,independent_score=.400001,accepted_seconds=500);d['comparison']=compare(d['rows'])
        self.assertEqual(verify(d)['paired_sign_two_sided_p'],1)
    def test_unknown(self):
        d=make();d['rows'][0]['valid_accepted_submission']=None;d['comparison']=compare(d['rows']);self.assertEqual(verify(d)['unknown'],1)
    def test_late_rejected(self):
        d=make();d['rows'][0].update(valid_accepted_submission=True,score=.4,independent_score=.4,accepted_seconds=2101);d['comparison']=compare(d['rows'])
        with self.assertRaises(ValueError):verify(d)
    def test_wrong_budget_rejected(self):
        d=make();d['rows'][0]['budget_seconds']=2200
        with self.assertRaises(ValueError):verify(d)
    def test_omitted_gpu_cost_rejected(self):
        d=make();d['allocation']['gpu_hours']=.5
        with self.assertRaises(ValueError):verify(d)

if __name__=='__main__':unittest.main()
