import importlib.util,json,tempfile,unittest
from pathlib import Path
p=Path(__file__).parents[1]/'scripts/task_feedback_upper_readout_20261002.py'
s=importlib.util.spec_from_file_location('upper_readout',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class ReadoutTest(unittest.TestCase):
 def fixture(self,r):
  schedule=[dict(index=3*i+j,start=i,task=['random-acts-of-pizza','tweet-sentiment-extraction'][i%2],arm=a,seed=102001+i,wave=j) for i in range(6) for j,a in enumerate('ABC')]
  (r/'plan.json').write_text(json.dumps({'schedule':schedule,'base_commit':'f'*40}))
 def result(self,r,i,value,status='completed',elapsed=1):
  ep=r/f'episode-{i}';ep.mkdir();(ep/'launch.json').write_text('{}');(ep/'closed.json').write_text('{"worker_deadline_reached":false}');(ep/'finished.json').write_text(json.dumps({'status':status}))
  a=ep/'action-0';a.mkdir();d={'step':0,'valid':value is not None,'metric':value,'execution_started':True,'exit_code':0 if value is not None else 1,'timed_out':False,'elapsed_seconds':elapsed,'exec_seconds':.1,'executed_code_sha256':'e'*64}
  (a/'result.json').write_text(json.dumps(d));return d
 def test_full_denominator_both_tasks_maximize(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r)
   for i,v in ((1,.5),(2,.6),(4,.4),(5,.7)):self.result(r,i,v)
   out=m.collect(r);self.assertEqual((out['planned'],out['closed'],len(out['rows'])),(18,4,18))
   self.assertAlmostEqual(out['comparisons'][0]['oriented_selected_difference'],.1);self.assertAlmostEqual(out['comparisons'][3]['oriented_selected_difference'],.3)
 def test_1200_deadline_not_old_1800(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,0,.5,elapsed=1200.01)
   with self.assertRaises(ValueError):m.collect(r)
 def test_early_infrastructure_failure_not_comparison(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,.5);self.result(r,2,.6,status='unknown');self.assertFalse(m.collect(r)['comparisons'][0]['both_closed'])
 def test_missing_not_zero(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,None);self.result(r,2,.6)
   c=m.collect(r)['comparisons'][0];self.assertIsNone(c['oriented_selected_difference']);self.assertEqual(c['validity_difference'],1)
 def test_missing_initial_not_equality(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,None);self.result(r,2,None);self.assertIsNone(m.collect(r)['comparisons'][0]['initial_metric_equal'])
 def test_failed_generation_usage_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,0,.5);a=r/'episode-0/action-1';a.mkdir();(a/'feedback.json').write_text('{}')
   z=m.collect(r)['rows'][0];self.assertIsNone(z['completion_tokens']);self.assertEqual(z['generation_attempts'],1)
 def test_own_initial_gain_and_final_are_distinct(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);self.result(r,1,.5);v=self.result(r,2,.4);a=r/'episode-2/action-1';a.mkdir();v.update(step=1,metric=.7,elapsed_seconds=2);(a/'result.json').write_text(json.dumps(v))
   c=m.collect(r)['comparisons'][0];self.assertAlmostEqual(c['oriented_gain_difference'],.3);self.assertAlmostEqual(c['oriented_selected_difference'],.2)
 def test_invalid_execution_cannot_be_scored_success(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);v=self.result(r,0,.5);v['execution_started']=False;(r/'episode-0/action-0/result.json').write_text(json.dumps(v))
   with self.assertRaises(ValueError):m.collect(r)
 def test_regression_retains_incumbent(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);v=self.result(r,0,.5);a=r/'episode-0/action-1';a.mkdir();v.update(step=1,metric=.3,elapsed_seconds=2);(a/'result.json').write_text(json.dumps(v))
   self.assertEqual(m.collect(r)['rows'][0]['selected_metric'],.5)
if __name__=='__main__':unittest.main()
