import unittest
from closed_gain_timing_20261016 import curve,pool_stats

class Timing(unittest.TestCase):
    def row(self,i,events,sign=-1,initial=.1,offset=0):
        return dict(index=i,task='fixture',arm='fixture',block=0,initial=initial,sign=sign,offset=offset,
                    valid_events=events,curve=curve(events,initial,sign))
    def test_empty_keeps_warm(self):
        self.assertEqual([x['score'] for x in curve([],.1,-1)],[.1]*4)
    def test_inclusive_deadline_and_late(self):
        c=curve([dict(elapsed=1020,score=.04),dict(elapsed=1800.01,score=.01)],.1,-1)
        self.assertEqual([x['score'] for x in c],[.1,.04,.04,.04])
    def test_direction_and_regression(self):
        c=curve([dict(elapsed=100,score=.6),dict(elapsed=500,score=.4)],.5,1)
        self.assertEqual([x['score'] for x in c],[.6]*4)
    def test_nonfinite_rejected(self):
        with self.assertRaises(AssertionError):curve([dict(elapsed=10,score=float('nan'))],.1,-1)
        with self.assertRaises(AssertionError):curve([dict(elapsed=-1,score=.1)],.1,-1)
    def test_records_use_wall_offset(self):
        rows=[self.row(0,[dict(elapsed=100,score=.05)],offset=20),self.row(1,[dict(elapsed=110,score=.04)]),self.row(2,[]),self.row(3,[])]
        p=pool_stats(rows)
        self.assertEqual(p['valid_returns'],2)
        self.assertEqual(p['pool_records'],1)
        self.assertEqual(p['last_record_at'],110)
    def test_ties_not_new_records(self):
        rows=[self.row(i,[dict(elapsed=100+i,score=.05)]) for i in range(4)]
        p=pool_stats(rows)
        self.assertEqual(p['pool_records'],1)
        self.assertEqual(p['above_initial'],4)
    def test_full_denominator(self):
        with self.assertRaises(AssertionError):pool_stats([self.row(0,[])])
    def test_late_gain(self):
        rows=[self.row(i,[dict(elapsed=1100,score=.02)]) for i in range(4)]
        p=pool_stats(rows)
        self.assertAlmostEqual(p['post_1020_gain'],.08)
        self.assertEqual(p['prefix_curves'][1]['median'],.1)

if __name__=='__main__':unittest.main()
