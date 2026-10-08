import unittest
from closed_gpu_utilization import weighted


class UtilizationTests(unittest.TestCase):
    def test_clipped_and_missing_edges(self):
        r=weighted([dict(time=1,utilization=20),dict(time=3,utilization=80),dict(time=4,utilization=0)],0,5)
        self.assertAlmostEqual(r['coverage_fraction'],.6)
        self.assertEqual(r['sampled_whole_card_utilization_percent'],40)
        self.assertEqual(r['largest_sample_interval_seconds'],2)

    def test_empty_is_missing_not_zero(self):
        self.assertIsNone(weighted([],0,2)['sampled_whole_card_utilization_percent'])
        self.assertEqual(weighted([],0,2)['coverage_fraction'],0)

    def test_invalid_not_silently_ignored(self):
        for values in ([dict(time=1,utilization=0),dict(time=1,utilization=0)],
                       [dict(time=1,utilization=float('nan')),dict(time=2,utilization=0)]):
            with self.assertRaises(ValueError):weighted(values,0,3)


if __name__=='__main__':unittest.main()
