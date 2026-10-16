import unittest
from closed_online_observability_20261016 import intervals, observation


class ObservabilityTests(unittest.TestCase):
    def test_released_partner_resets_solo_reference(self):
        events = [dict(event=event, key=k, device=0, time=t) for event, k, t in [
            ('admitted','0:0',0), ('admitted','1:0',10), ('released','1:0',20),
            ('admitted','2:0',30), ('released','0:0',40), ('released','2:0',50)]]
        leases, admissions = intervals(events)
        self.assertEqual([r['preceding_solo_start'] for r in admissions], [0,20])
        self.assertEqual(leases['0:0']['end'],40)

    def test_windows_use_no_future_reference(self):
        a = [dict(start=i,end=i+.5) for i in range(100)]
        b = [dict(start=i/100+40,end=i/100+40.001) for i in range(32)]
        e = dict(preceding_solo_start=0, admitted_at=40)
        out = observation(a,b,e,100,32)
        self.assertTrue(out['sufficient'])
        self.assertAlmostEqual(out['host_call_rate_ratio'],1)
        self.assertEqual(out['incumbent_pre_steps_available'],40)

    def test_insufficient_not_zero_slowdown(self):
        out=observation([dict(start=0,end=1)],[],dict(preceding_solo_start=0,admitted_at=2),4,32)
        self.assertFalse(out['sufficient'])
        self.assertNotIn('host_call_rate_ratio',out)

    def test_threshold_and_partner_end(self):
        a=[dict(start=i,end=i+.5) for i in range(40)] + [dict(start=100+2*i,end=101+2*i) for i in range(40)]
        b=[dict(start=50+i,end=50.5+i) for i in range(32)]
        e=dict(preceding_solo_start=0,admitted_at=40)
        out=observation(a,b,e,180,32)
        self.assertTrue(out['host_rate_drop_over_35_percent'])
        self.assertFalse(observation(a,b,e,110,32)['sufficient'])


if __name__=='__main__': unittest.main()
