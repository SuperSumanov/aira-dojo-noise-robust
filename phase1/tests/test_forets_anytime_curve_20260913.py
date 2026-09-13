from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_forets_anytime_curve_20260913 import choose_prefix,CUTOFFS


class CurveTests(unittest.TestCase):
    def test_fixed_cutoffs(self):self.assertEqual(CUTOFFS,(120,240,360,480,600))
    def test_exact_cutoff_excluded(self):
        r=dict(step=2,durable_ns=120*10**9+1,eligible=True)
        self.assertIsNone(choose_prefix([r],1,120))
    def test_missing_is_missing(self):self.assertIsNone(choose_prefix([],1,600))
    def test_select_latest_not_highest_external_grade(self):
        rs=[dict(step=2,durable_ns=20*10**9,eligible=True,grade=1.),
            dict(step=4,durable_ns=100*10**9,eligible=True,grade=.1),
            dict(step=6,durable_ns=121*10**9,eligible=True,grade=2.)]
        self.assertEqual(choose_prefix(rs,1,120)['step'],4)
    def test_uncertified_record_ignored(self):
        self.assertIsNone(choose_prefix([dict(step=2,durable_ns=5,eligible=False)],1,600))


if __name__=='__main__':unittest.main()
