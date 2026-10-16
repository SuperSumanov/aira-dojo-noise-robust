import unittest
from diverse_pool_20261017 import State,task_of,independent_audit


class Tests(unittest.TestCase):
    def seeded(self,mode):
        s=State(mode)
        for key in ('0:0','2:0','1:0','3:0'):
            s.request(key,0);s.admit(key)
        return s
    def test_empty_before_partner_preference(self):
        s=State('diverse');s.request('0:0',0);self.assertEqual(s.admit('0:0'),0)
        s.request('1:0',0);self.assertEqual(s.admit('1:0'),1)
    def test_only_device_tie_break_changes(self):
        a,b=self.seeded('colocated'),self.seeded('diverse')
        a.request('4:0',0);b.request('4:0',0)
        self.assertEqual(a.admit('4:0'),0);self.assertEqual(b.admit('4:0'),2)
    def test_fifo_not_reordered(self):
        s=self.seeded('diverse');s.request('4:0',0);s.request('5:0',0)
        self.assertIsNone(s.admit('5:0'))
    def test_fallback_not_blocking(self):
        s=State('diverse')
        for i in range(4):s.request(f'{i*2}:0',0);s.admit(f'{i*2}:0')
        s.request('8:0',0);self.assertEqual(s.admit('8:0'),0)
    def test_full_capacity_and_release(self):
        s=State('diverse')
        for i in range(8):s.request(f'{i}:0',0);self.assertIsNotNone(s.admit(f'{i}:0'))
        s.request('8:0',0);self.assertIsNone(s.admit('8:0'))
        s.release('0:0',True);self.assertIsNotNone(s.admit('8:0'))
    def test_same_state_serialization(self):
        s=self.seeded('diverse');self.assertEqual(State(**s.value()).value(),s.value())
    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):task_of('not-an-episode')
    def test_trace_replay_and_wrong_dispatch_rejected(self):
        s=State('diverse');es=[];clock=0
        def emit(kind,key,device=None):
            nonlocal clock
            clock+=1;es.append(dict(event=kind,key=key,home=0,device=device,time=clock,queued=len(s.queue),active=len(s.active)))
        for key in ('0:0','2:0','1:0','3:0','4:0'):
            s.request(key,0);emit('queued',key);d=s.admit(key);emit('admitted',key,d)
        for key in list(s.active):
            d=s.active[key]['device'];s.release(key,True);emit('released',key,d)
        self.assertEqual(independent_audit(es,'diverse')['changed_device_choices'],1)
        with self.assertRaises(AssertionError):independent_audit(es,'colocated')
    def test_shared_cap_unchanged(self):
        s=self.seeded('shared');s.request('4:0',0);self.assertIsNone(s.admit('4:0'))


if __name__=='__main__':unittest.main()
