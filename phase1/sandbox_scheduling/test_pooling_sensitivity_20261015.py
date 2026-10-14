import unittest
from pooling_sensitivity_20261015 import replay, summarize, balanced_pairs
from pooling_structure_export_20261015 import session

def job(s,t=0,d=10,deadline=20):
    return dict(session=s,task=s%2,lane=s//2,arrival=t,duration=d,deadline=deadline)

class PoolingTest(unittest.TestCase):
    def test_balanced_count(self):
        maps=list(balanced_pairs([job(s) for s in range(8)]))
        self.assertEqual(len(maps),24)
        self.assertEqual(len({tuple(sorted(m.items())) for m in maps}),24)
        for m in maps:
            for lane in range(4):self.assertEqual({s%2 for s,l in m.items() if l==lane},{0,1})
    def test_same_lane_contention(self):
        jobs=[job(0),job(1)]
        fixed=summarize(replay(jobs,{0:0,1:0}));pooled=summarize(replay(jobs))
        self.assertEqual(fixed['total_wait_seconds'],10)
        self.assertEqual(pooled['total_wait_seconds'],0)
    def test_charge_dispatch(self):
        rows=replay([job(0,deadline=12)],overhead=3)
        self.assertEqual(rows[0]['flow'],13)
        self.assertFalse(rows[0]['by_deadline'])
    def test_equal_arrival_not_duration_ordered(self):
        jobs=[job(s,d=100 if s==0 else 1) for s in range(5)]
        rows=replay(jobs)
        self.assertEqual([r['index'] for r in rows],list(range(5)))
        self.assertEqual(rows[4]['begin'],1)
    def test_original_index_stable(self):
        rows=replay([job(1,t=2),job(0,t=0)])
        self.assertEqual([r['index'] for r in rows],[1,0])
    def test_release_deadline_inclusive(self):
        self.assertTrue(replay([job(0,d=10,deadline=10)])[0]['by_deadline'])
    def test_unknown_schema(self):
        for k in ['x:1','1:2:3','1','1:']:
            with self.assertRaises(ValueError):session(k)
        self.assertEqual(session('40:2'),40)
    def test_empty_session_no_exclusion(self):
        self.assertEqual(len(list(balanced_pairs([job(0)]))),24)

if __name__=='__main__':unittest.main()
