import importlib.util,json,tempfile,unittest
from pathlib import Path
p=Path(__file__).parents[1]/'scripts/task_feedback_readout_20261001.py';s=importlib.util.spec_from_file_location('readout',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ReadoutTest(unittest.TestCase):
 def fixture(self,root):
  schedule=[dict(index=3*i+j,start=i,task=['spooky-author-identification','random-acts-of-pizza','tweet-sentiment-extraction'][i%3],arm=a,seed=i,wave=j) for i in range(6) for j,a in enumerate('ABC')]
  (root/'plan.json').write_text(json.dumps({'schedule':schedule,'base_commit':'f'*40}))
 def result(self,r,i,*,metric,status='completed',late=False):
  e=r/f'episode-{i}';e.mkdir();(e/'launch.json').write_text('{}');(e/'finished.json').write_text(json.dumps({'status':status}));(e/'closed.json').write_text(json.dumps({'worker_deadline_reached':False}))
  a=e/'action-0';a.mkdir();v={'step':0,'valid':metric is not None,'execution_started':True,'exit_code':0 if metric is not None else 1,'timed_out':False,'metric':metric,'elapsed_seconds':1801 if late else 1,'exec_seconds':.5,'executed_code_sha256':'e'*64}
  (a/'result.json').write_text(json.dumps(v))
 def test_all_denominators_and_directions(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,metric=.5);self.result(r,2,metric=.4)
   out=m.collect(r);self.assertEqual(out['planned'],18);self.assertEqual(len(out['rows']),18);self.assertEqual(out['closed'],2)
   self.assertAlmostEqual(out['comparisons'][0]['oriented_selected_difference'],.1)
   self.assertFalse(out['comparisons'][1]['both_closed'])
 def test_infrastructure_unknown_is_not_complete(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,metric=.5);self.result(r,2,metric=.4,status='unknown')
   self.assertFalse(m.collect(r)['comparisons'][0]['both_closed'])
 def test_late_result_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,0,metric=.5,late=True)
   with self.assertRaises(ValueError):m.collect(r)
 def test_missing_result_not_a_zero_score(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,metric=None);self.result(r,2,metric=.4)
   out=m.collect(r);pair=out['comparisons'][0]
   self.assertTrue(pair['both_closed']);self.assertFalse(pair['both_valid']);self.assertIsNone(pair['oriented_selected_difference']);self.assertEqual(pair['validity_difference'],1)
 def test_failed_request_usage_is_unknown_not_zero(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,0,metric=.5)
   a=r/'episode-0/action-1';a.mkdir();(a/'feedback.json').write_text('{}')
   row=m.collect(r)['rows'][0]
   self.assertEqual(row['generation_attempts'],1);self.assertEqual(row['unknown_usage_attempts'],1);self.assertIsNone(row['prompt_tokens']);self.assertIsNone(row['completion_tokens'])
 def test_two_missing_initial_metrics_are_not_equality_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,metric=None);self.result(r,2,metric=None)
   self.assertIsNone(m.collect(r)['comparisons'][0]['initial_metric_equal'])
 def test_gain_contrast_is_separate_from_raw_final_difference(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,metric=.5);self.result(r,2,metric=.6)
   a=r/'episode-2/action-1';a.mkdir();v=json.loads((r/'episode-2/action-0/result.json').read_text());v.update(step=1,metric=.3,elapsed_seconds=2);(a/'result.json').write_text(json.dumps(v))
   c=m.collect(r)['comparisons'][0]
   self.assertAlmostEqual(c['oriented_gain_difference'],.3);self.assertAlmostEqual(c['oriented_selected_difference'],.2);self.assertFalse(c['initial_metric_equal'])
if __name__=='__main__':unittest.main()
