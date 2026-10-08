import unittest
from live_admission import AdmissionState, audit_events


class AdmissionTests(unittest.TestCase):
    def test_width_one_fifo(self):
        s=AdmissionState(1)
        s.request('a');s.request('b')
        self.assertFalse(s.admit('b'))
        self.assertTrue(s.admit('a'))
        self.assertFalse(s.admit('b'))
        with self.assertRaises(ValueError):s.finish('a',cleanup_verified=False)
        self.assertEqual(s.active,['a'])
        s.finish('a',cleanup_verified=True)
        self.assertTrue(s.admit('b'))

    def test_width_two_never_three(self):
        s=AdmissionState(2)
        for k in ('a','b','c'):s.request(k)
        self.assertTrue(s.admit('a'));self.assertTrue(s.admit('b'))
        self.assertFalse(s.admit('c'))
        s.finish('b',cleanup_verified=True)
        self.assertTrue(s.admit('c'))

    def test_cancel_is_not_release(self):
        s=AdmissionState(1);s.request('a');s.request('b');s.admit('a')
        with self.assertRaises(ValueError):s.cancel_waiting('a')
        s.cancel_waiting('b')
        self.assertEqual(s.active,['a'])
        with self.assertRaises(ValueError):s.request('b')

    def test_invalid_state(self):
        for args in ({'limit':0},{'limit':1,'queue':['a'],'active':['a']},
                     {'limit':1,'active':['a','b']}):
            with self.assertRaises(ValueError):AdmissionState(**args)

    def test_replay_detects_wrong_counts(self):
        events=[dict(event='queued',key='a',time=0,queued=1,active=0,limit=1),
                dict(event='admitted',key='a',time=1,queued=0,active=1,limit=1),
                dict(event='released',key='a',time=2,queued=0,active=0,limit=1)]
        self.assertTrue(audit_events(events,1)['all_released'])
        events[-1]['active']=1
        with self.assertRaises(ValueError):audit_events(events,1)

if __name__=='__main__':unittest.main()
