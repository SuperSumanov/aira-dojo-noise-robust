import unittest
from watch_current_trials import compact


class WatchTests(unittest.TestCase):
    def test_neural_omits_elapsed_and_values_preserves_failure(self):
        state={'job':'1','blocks_complete':0,'rows':[dict(index=0,arm='pipeline',started=True,closed=True,complete=False,error_type='TimeoutError',returncode=1,native_score=.9,elapsed_since_worker_start=10)]}
        view=compact('neural',state)
        self.assertEqual(view['completed'],0)
        self.assertEqual(view['rows'][0]['error_type'],'TimeoutError')
        self.assertNotIn('native_score',view['rows'][0])
        state['rows'][0]['elapsed_since_worker_start']=20
        self.assertEqual(compact('neural',state),view)
    def test_warmup_not_in_denominator(self):
        view=compact('neural',dict(job='1',blocks_complete=0,rows=[dict(index=36,started=True,complete=True)]))
        self.assertEqual(view['completed'],0)
    def test_live_does_not_export_scores(self):
        state=dict(launch={'job':'2'},controller_closed={},blocks=[dict(block=0,service_ready={},worker_started=1,worker_finished=0,supervisor_closed=0,candidate_receipts=1,scoring_receipts=1,cycle_closed=False,budget_slot={},gpu_clean=None,worker_states=[dict(index=0,status='running',native_score=.9)],service_log=None,block_log=None)])
        self.assertNotIn('native_score',compact('twochild',state)['blocks'][0]['states'][0])


if __name__=='__main__':unittest.main()
