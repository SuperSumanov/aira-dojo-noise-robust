import unittest
from stack_capture_evidence import stack_evidence,gpu_evidence

class Tests(unittest.TestCase):
    def test_parent_wait_not_background_queue(self):
        raw='''Timeout (0:00:30)!
Thread 0xaaaa (most recent call first):
  File "/usr/lib/python3.12/queue.py", line 100 in get
Thread 0xbbbb (most recent call first):
  File "/opt/lib/torch/utils/data/dataloader.py", line 200 in _try_get_data
  File "/tmp/ipykernel_123/secret_candidate.py", line 3 in private_name
  File "/opt/lib/IPython/core/interactiveshell.py", line 1 in run_code
'''
        out=stack_evidence(raw);threads=out['dumps'][0]['threads']
        self.assertEqual([t['category'] for t in threads],['other','dataloader_wait'])
        self.assertNotIn('private_name',str(out));self.assertNotIn('secret_candidate',str(out))
    def test_out_of_window_and_missing_are_not_zero(self):
        rows=[dict(time=0,query_ok=True,values={'utilization.gpu':'100'}),dict(time=2,query_ok=False),dict(time=3,query_ok=True,values={'utilization.gpu':'[N/A]'})]
        out=gpu_evidence(rows,1,4);self.assertEqual(out['samples_in_call'],2);self.assertIsNone(out['utilization_median'])
    def test_numeric_summary(self):
        out=gpu_evidence([dict(time=t,query_ok=True,values={'utilization.gpu':str(u)}) for t,u in [(1,0),(3,10),(5,20)]],0,6)
        self.assertEqual(out['utilization_median'],10);self.assertEqual(out['maximum_sample_gap'],2)
        self.assertAlmostEqual(out['sample_span_fraction'],4/6)

if __name__=='__main__':unittest.main()
