import copy,unittest
from readout_comparison_online_continuation_20260919 import compare

def fixture():
    return [dict(index=i,seed=i//2+1,cache=i%2==i//2,valid_accepted_submission=False,score=None,accepted_seconds=None) for i in range(4)]

class PairedReadout(unittest.TestCase):
    def test_no_submission_is_not_positive(self):
        result=compare(fixture());self.assertEqual(result['paired_validity_mean_delta'],0)
    def test_one_rescue_is_one_pair_not_four_seeds(self):
        rows=fixture();rows[0].update(valid_accepted_submission=True,score=.4,accepted_seconds=20)
        result=compare(rows);self.assertEqual(result['physical_runs'],2);self.assertEqual(result['paired_validity_mean_delta'],.5)
    def test_negative_pair_retained(self):
        rows=fixture();rows[1].update(valid_accepted_submission=True,score=.4,accepted_seconds=20)
        self.assertEqual(compare(rows)['paired_validity_mean_delta'],-.5)
    def test_unknown_not_counted_as_failure(self):
        rows=fixture();rows[0]['valid_accepted_submission']=None
        self.assertIsNone(compare(rows)['paired_validity_mean_delta'])
    def test_both_valid_quality_and_time_deltas(self):
        rows=fixture();rows[0].update(valid_accepted_submission=True,score=.35,accepted_seconds=50);rows[1].update(valid_accepted_submission=True,score=.4,accepted_seconds=100)
        group=compare(rows)['groups'][0];self.assertAlmostEqual(group['loss_delta_cache_minus_baseline'],-.05);self.assertEqual(group['first_accept_seconds_delta'],-50)
    def test_incomplete_pairs_rejected(self):
        with self.assertRaises(ValueError):compare(fixture()[:3])

if __name__=='__main__':unittest.main()
