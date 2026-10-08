import unittest
from feedback_latency import block_metrics

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

if __name__=='__main__':unittest.main()
