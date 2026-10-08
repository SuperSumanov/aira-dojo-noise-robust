import unittest
from live_phase_analysis import phases, length_union


class PhaseTests(unittest.TestCase):
    def test_interval_union_clips_deadline(self):
        self.assertEqual(length_union([(-2, 3), (2, 8), (12, 15)], 10), 8)

    def test_disjoint_accounting(self):
        e = [dict(event='kernel_ready', elapsed=10., seconds=10.),
             dict(event='admitted', elapsed=20., wait_seconds=10., operation=0),
             dict(event='released', elapsed=40., operation=0),
             dict(event='generation_started', elapsed=45., call=0),
             dict(event='generation_returned', elapsed=70., call=0, seconds=25.)]
        result = phases(e, 100.)
        self.assertEqual(result['seconds'], dict(generation=25., kernel_readiness=10., queue=10., lease=20.))
        self.assertEqual(result['unclassified_within_observation_seconds'], 5.)
        self.assertEqual(result['budget_after_last_event_seconds'], 30.)
        self.assertEqual(result['cross_phase_overlap_seconds'], 0.)
        self.assertTrue(result['complete'])

    def test_unfinished_is_not_imputed(self):
        result = phases([dict(event='generation_started', elapsed=20., call=0)], 100.)
        self.assertFalse(result['complete'])
        self.assertEqual(result['seconds']['generation'], 0.)
        self.assertEqual(result['unfinished'], {'generation': 1})

    def test_cancelled_wait_is_counted_without_lease(self):
        e = [dict(event='admission_interrupted', elapsed=100., wait_seconds=20., held=False, operation=0)]
        self.assertEqual(phases(e, 100.)['seconds']['queue'], 20.)
        self.assertEqual(phases(e, 100.)['seconds']['lease'], 0.)

    def test_backward_or_missing_start_fail(self):
        with self.assertRaises(ValueError):
            phases([dict(event='released', elapsed=20., operation=0)])
        with self.assertRaises(ValueError):
            phases([dict(event='other', elapsed=20.), dict(event='other', elapsed=10.)])


if __name__ == '__main__':
    unittest.main()
