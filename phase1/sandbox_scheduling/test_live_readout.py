import copy
import unittest
from live_search_trial_20261009 import schedule
from live_readout import summarize,queue_verify,ground_scores


class ReadoutTests(unittest.TestCase):
    def fixture(self):
        rows=[dict(**r,complete=True,native_valid=True,native_score=.5,
                   valid_returns=2 if r['arm']=='share2' else 1) for r in schedule()]
        blocks=[dict(block=i,attempted=True,closed=True,identities_ok=True,queue={'complete':True}) for i in range(4)]
        return rows,blocks

    def test_neither_arm_started_is_missing_not_tie(self):
        r,b=self.fixture()
        for row in r:row.update(complete=False,native_valid=False,native_score=None,valid_returns=0)
        for block in b:block.update(attempted=False,closed=False)
        result=summarize(r,b)
        self.assertEqual(result['assigned_pool_return_count_differences'],[0,0])
        self.assertEqual(result['paired_pool_valid_return_differences'],[None,None])
        self.assertIsNone(result['pool_difference_median'])
        self.assertIsNone(result['pool_difference_sample_std'])
        self.assertFalse(result['exploratory_go'])

    def test_unstarted_comparator_not_treated_as_zero(self):
        r,b=self.fixture();b[1]['attempted']=False
        for row in r:
            if row['block']==1:row.update(complete=False,native_valid=False,native_score=None,valid_returns=0)
        result=summarize(r,b)
        self.assertEqual(result['paired_pool_valid_return_differences'],[None,4])
        self.assertIsNone(result['pool_difference_median'])
        self.assertEqual(result['observed_pool_pairs'],1)
        self.assertFalse(result['exploratory_go'])

    def test_complete_favorable_fixture(self):
        r,b=self.fixture();s=summarize(r,b)
        self.assertEqual(s['paired_pool_valid_return_differences'],[4,4])
        self.assertTrue(s['exploratory_go'])

    def test_missing_quality_is_not_ignored(self):
        r,b=self.fixture();r[0]['native_valid']=False;r[0]['native_score']=None
        self.assertFalse(summarize(r,b)['exploratory_go'])
        self.assertFalse(summarize(r,b)['all_eight_score_pairs_observed'])

    def test_missing_block_or_endpoint_fails(self):
        r,b=self.fixture();self.assertFalse(summarize(r,b[:3])['exploratory_go'])
        r[0]['complete']=False;self.assertFalse(summarize(r,b)['exploratory_go'])

    def test_one_pool_tie_fails(self):
        r,b=self.fixture()
        for row in r:
            if row['repeat']==1:row['valid_returns']=1
        self.assertFalse(summarize(r,b)['exploratory_go'])

    def test_task_orientation(self):
        r,b=self.fixture()
        for row in r:
            if row['arm']=='share2' and row['task']=='spooky-author-identification':row['native_score']=.6
        self.assertLess(summarize(r,b)['paired_task_medians']['spooky-author-identification'],0)
        self.assertFalse(summarize(r,b)['exploratory_go'])

    def test_queue_independent_replay(self):
        e=[dict(time=0,event='queued',key='a',queued=1,active=0,limit=1),
           dict(time=1,event='admitted',key='a',queued=0,active=1,limit=1),
           dict(time=3,event='released',key='a',queued=0,active=0,limit=1)]
        self.assertEqual(queue_verify(e,1)['queue_seconds'],1)
        self.assertEqual(queue_verify(e,1)['lease_seconds'],2)
        broken=copy.deepcopy(e);broken[2]['key']='b'
        with self.assertRaises(ValueError):queue_verify(broken,1)

    def test_selected_score_requires_timely_external_receipt(self):
        final=dict(native_selected_valid=True,native_selected_score=.6,native_selected_code_sha256='code')
        candidate=dict(valid=True,code_sha256='code',score=.6,
                       aux={'submission_sha256':'submission','metric_name':'auc'})
        receipts=[{'submission_sha256':'submission','auc':.6}]
        self.assertTrue(ground_scores(final,[candidate],receipts))
        self.assertFalse(ground_scores(final,[],receipts))
        final['native_selected_score']=.7
        self.assertFalse(ground_scores(final,[candidate],receipts))
        with self.assertRaises(ValueError):ground_scores(final,[candidate],[])

if __name__=='__main__':unittest.main()
