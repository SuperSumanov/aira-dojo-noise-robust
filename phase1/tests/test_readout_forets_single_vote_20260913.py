import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_forets_single_vote_20260913 import rank_timings

class SingleVoteReadoutTests(unittest.TestCase):
    def test_empty_pool_and_interrupted_vote_not_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.assertEqual(rank_timings(root)['completed_pools'],0)
            p=root/'batch-1';p.mkdir()
            (p/'input.json').write_text(json.dumps(dict(aggregation='single_order_rank_v1',orders=[[0,1,2,3]],codes_sha256=['a','b','c','d'])))
            result=rank_timings(root)
            self.assertEqual(result['unfinished_pools'],['batch-1']);self.assertIsNone(result['median_seconds'])
    def test_one_vote_timing_and_second_vote_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'batch-1';p.mkdir()
            (p/'input.json').write_text(json.dumps(dict(aggregation='single_order_rank_v1',orders=[[0,1,2,3]],codes_sha256=['a','b','c','d'])))
            done=dict(paid_calls=1,rankings=[[3,2,1,0]],model='qwen/qwen3-coder-plus',observed_task_outcomes=False,
                top2_order_invariant=None,borda=[1.,2.,3.,4.],rank_timings=[dict(order_index=0,request_through_parse_seconds=7.5)])
            (p/'finished.json').write_text(json.dumps(done));self.assertEqual(rank_timings(root)['median_seconds'],7.5)
            (p/'request-1.json').write_text('{}')
            with self.assertRaises(ValueError):rank_timings(root)

if __name__=='__main__':unittest.main()
