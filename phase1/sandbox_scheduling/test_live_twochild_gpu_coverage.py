import unittest
from live_twochild_gpu_coverage import summarize


class CoverageTests(unittest.TestCase):
    def test_idle_is_observed_not_unseen_padding(self):
        samples=[dict(time=t,utilization=0,memory_mib=0,pids=[]) for t in (1,2,3)]
        row=summarize(samples,0,4)
        self.assertEqual(row['coverage_fraction'],.5)
        self.assertEqual(row['nonzero_utilization_samples'],0)
        self.assertEqual(row['covered_seconds'],2)
    def test_nonzero_and_no_pid_export(self):
        samples=[dict(time=t,utilization=u,memory_mib=128,pids=[123]) for t,u in ((0,0),(1,50),(2,100))]
        row=summarize(samples,0,2)
        self.assertEqual(row['nonzero_utilization_samples'],2)
        self.assertEqual(row['sampled_whole_card_utilization_percent'],25)
        self.assertNotIn('pids',row)
    def test_missing_and_malformed_rejected(self):
        with self.assertRaises(ValueError):summarize([],0,2)
        for value in (-1,101,float('nan')):
            with self.assertRaises(ValueError):summarize([dict(time=0,utilization=value,memory_mib=0,pids=[])],0,2)


if __name__=='__main__':unittest.main()
