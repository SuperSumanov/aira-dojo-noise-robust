import unittest
from effort_pressure_diagnostic_20261012 import state_changes,integrate


class PressureTest(unittest.TestCase):
    def test_overlap_not_sum(self):
        g=[(1,0,1),(6,0,0)];e=[(3,0,1),(8,0,0)]
        r=integrate([g,e],0,10)
        self.assertEqual([r[k+'_seconds'] for k in ('generation_only','both','execution_only','neither')],[2,3,2,3])
        self.assertEqual(r['generation_held_seconds'],5)
        self.assertEqual(r['execution_held_seconds'],5)

    def test_queue_area_cancel(self):
        events=[dict(time=t,key=k,kind=kind) for t,k,kind in [(0,'a','queued'),(1,'a','admitted'),(2,'b','queued'),(4,'b','cancelled'),(5,'a','released')]]
        changes,a=state_changes(events,1);r=integrate([changes],0,6)
        self.assertEqual(a['waiting_seconds'],3)
        self.assertEqual(a['holding_seconds'],4)
        self.assertEqual(r['generation_queued_seconds'],3)

    def test_bad_trace(self):
        for events in [[dict(time=1,key='a',kind='released')],
                       [dict(time=1,key='a',kind='queued')],
                       [dict(time=2,key='a',kind='queued'),dict(time=1,key='a',kind='cancelled')]]:
            with self.assertRaises(ValueError):state_changes(events,1)

    def test_outside_window(self):
        with self.assertRaises(ValueError):integrate([[(11,0,1)]],0,10)

    def test_simultaneous_states(self):
        r=integrate([[(1,0,4),(2,0,0)],[(1,0,1),(2,0,0)]],0,3)
        self.assertEqual(r['both_seconds'],1)
        self.assertEqual(r['generation_full_seconds'],1)
        self.assertEqual(r['neither_seconds'],2)


if __name__=='__main__':unittest.main()
