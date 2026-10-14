import unittest
from compute_split_screen_20261015 import telemetry, jobs, replay_fixed_arrivals, simultaneous

class ScreenTest(unittest.TestCase):
    def test_sample_weighted_and_no_extrapolation(self):
        s=[dict(time=t,utilization=u,memory_mib=1) for t,u in [(1,100),(2,0),(5,50)]]
        r=telemetry(s,0,10)
        self.assertEqual(r['window_coverage'],.4)
        self.assertEqual(r['utilization_time_weighted_pct'],25)
    def test_bad_clock(self):
        s=[dict(time=1,utilization=0,memory_mib=1)]*2
        with self.assertRaises(ValueError):telemetry(s,0,5)
    def test_fixed_arrivals(self):
        work=[dict(arrival=0,original_start=0,duration=4)]*4
        self.assertEqual(replay_fixed_arrivals(work,4,5)['finishes_by_pool_end'],4)
        self.assertEqual(replay_fixed_arrivals(work,2,5)['finishes_by_pool_end'],2)
        self.assertEqual(replay_fixed_arrivals(work,2,5)['total_wait_seconds'],8)
    def test_cancel_not_imputed_execution(self):
        events=[dict(time=t,key=k,kind=e) for t,k,e in [(0,'a','queued'),(1,'a','admitted'),(2,'b','queued'),(3,'b','cancelled'),(4,'a','released')]]
        self.assertEqual(jobs(events),[dict(arrival=0,original_start=1,duration=3)])
    def test_unknown_release(self):
        with self.assertRaises(KeyError):jobs([dict(time=1,key='a',kind='released')])
    def test_state_intersection(self):
        streams=[[(1,1,4),(5,0,0)],[(2,0,1),(6,0,0)]]
        r=simultaneous(streams,0,8)
        self.assertEqual(r['gen_wait_with_at_most_two_exec_seconds'],4)
        self.assertEqual(r['gen_wait_with_zero_exec_seconds'],1)
    def test_same_timestamp(self):
        streams=[[(0,1,0),(0,0,1),(2,0,0)],[(0,0,0)]]
        self.assertEqual(simultaneous(streams,0,3)['gen_wait_seconds'],0)
    def test_no_jobs(self):
        self.assertEqual(replay_fixed_arrivals([],2,5)['last_finish_past_end'],0)

if __name__=='__main__':unittest.main()
