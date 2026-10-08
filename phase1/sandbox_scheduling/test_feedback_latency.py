import unittest
from feedback_latency import block_metrics,paired_metrics

class LatencyTests(unittest.TestCase):
 def test_block_clock_origin_and_first_return(self):
  result=block_metrics(10,50,[{'end':48,'success':True},{'end':25,'success':True}])
  self.assertEqual(result['first_completed_return'],15)
  self.assertEqual(result['mean_completed_return'],26.5)
  self.assertEqual(result['makespan'],40)
 def test_failed_block_kept_but_no_complete_mean(self):
  result=block_metrics(10,50,[{'end':20,'success':False},{'end':45,'success':True}])
  self.assertFalse(result['complete']);self.assertEqual(result['completed'],1)
  self.assertEqual(result['first_completed_return'],35)
  self.assertIsNone(result['mean_completed_return'])
 def test_invalid_times_rejected(self):
  with self.assertRaises(ValueError):block_metrics(10,50,[{'end':9,'success':True},{'end':45,'success':True}])

 def test_pipeline_reference_cannot_be_mislabeled_serial(self):
  blocks=[dict(program=None,repeat=0,arm=arm,complete=True,makespan=t,
               first_completed_return=t/2,mean_completed_return=3*t/4)
          for arm,t in [('pipeline',120),('share2',100)]]
  pairs=paired_metrics(blocks,'pipeline')
  self.assertEqual(pairs[0]['pipeline_over_share2_makespan'],1.2)
  self.assertNotIn('serial_over_share2_makespan',pairs[0])
  self.assertEqual(paired_metrics(blocks,'serial'),[])
  blocks[1]['complete']=False
  self.assertEqual(paired_metrics(blocks,'pipeline'),[])

 def test_duplicate_arm_is_not_silently_overwritten(self):
  block=dict(program=None,repeat=0,arm='serial',complete=True)
  with self.assertRaises(ValueError):paired_metrics([block,block],'serial')

 def test_unknown_reference_rejected(self):
  with self.assertRaises(ValueError):paired_metrics([],'best_after_result')

if __name__=='__main__':unittest.main()
