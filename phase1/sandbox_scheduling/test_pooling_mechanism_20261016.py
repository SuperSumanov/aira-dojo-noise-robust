import unittest
from pooling_mechanism_20261016 import integrate

class Integration(unittest.TestCase):
    def test_constant(self):
        r=integrate([dict(time=0,utilization=20),dict(time=2,utilization=0)],0,2)
        self.assertEqual(r["utilization_pct"],20)
        self.assertEqual(r["coverage"],1)
    def test_partial_not_extrapolated(self):
        r=integrate([dict(time=1,utilization=80),dict(time=3,utilization=0)],0,4)
        self.assertEqual(r["coverage"],.5)
        self.assertEqual(r["utilization_pct"],80)
    def test_clip(self):
        r=integrate([dict(time=0,utilization=0),dict(time=2,utilization=100),
                     dict(time=4,utilization=20)],1,3)
        self.assertEqual(r["utilization_pct"],50)
        self.assertEqual(r["nonzero_fraction"],.5)
    def test_bad_time(self):
        with self.assertRaises(AssertionError):
            integrate([dict(time=1,utilization=0),dict(time=1,utilization=0)],0,2)
    def test_bad_utilization(self):
        with self.assertRaises(AssertionError):
            integrate([dict(time=0,utilization=101),dict(time=1,utilization=0)],0,2)

if __name__=="__main__":unittest.main()
