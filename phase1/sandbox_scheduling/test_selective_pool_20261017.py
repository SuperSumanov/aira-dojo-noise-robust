import unittest
from selective_pool_20261017 import State,independent_audit


class Tests(unittest.TestCase):
    def full(self,keys=('0:a','2:a','4:a','6:a')):
        s=State('selective')
        for i,k in enumerate(keys):s.request(k,i);self.assertEqual(s.admit(k),i)
        return s
    def test_aerial_can_share(self):
        s=self.full();s.request('8:a',1);self.assertEqual(s.admit('8:a'),0)
    def test_denoise_is_exclusive(self):
        s=self.full();s.request('9:a',1);self.assertIsNone(s.admit('9:a'))
    def test_denoise_incumbent_cannot_receive_aerial(self):
        s=self.full(('1:a','3:a','5:a','7:a'));s.request('8:a',1);self.assertIsNone(s.admit('8:a'))
    def test_mixed_pool_chooses_unprotected(self):
        s=self.full(('1:a','3:a','4:a','6:a'));s.request('8:a',1);self.assertEqual(s.admit('8:a'),2)
    def test_empty_first(self):
        s=State('selective');s.request('0:a',3);s.admit('0:a');s.request('2:a',3);self.assertEqual(s.admit('2:a'),1)
    def test_fifo_not_bypassed(self):
        s=self.full();s.request('9:a',0);s.request('10:a',1);self.assertIsNone(s.admit('10:a'))
    def test_shared_cap_unchanged(self):
        s=State('shared')
        for i in range(4):s.request(str(i),i);s.admit(str(i))
        s.request('8:a',0);self.assertIsNone(s.admit('8:a'))
    def test_illegal_restored_state_rejected(self):
        with self.assertRaises(ValueError):State('selective',active={'1:a':dict(device=0,home=0),'2:a':dict(device=0,home=1)})
    def test_bad_prefix_rejected(self):
        with self.assertRaises(ValueError):State('selective').request('bad',0)
    def test_independent_queue(self):
        es=[];keys=['0:a','2:a','4:a','6:a','8:a'];s=State('selective')
        for i,k in enumerate(keys):
            s.request(k,i%4);es.append(dict(event='queued',key=k,home=i%4,time=len(es),queued=len(s.queue),active=len(s.active)))
            d=s.admit(k);es.append(dict(event='admitted',key=k,device=d,time=len(es),queued=len(s.queue),active=len(s.active)))
        for k in keys:
            d=s.active[k]['device'];s.release(k,True);es.append(dict(event='released',key=k,device=d,time=len(es),queued=0,active=len(s.active)))
        self.assertEqual(independent_audit(es,'selective')['co_admissions'],1)
        with self.assertRaises(AssertionError):independent_audit(es,'shared')


if __name__=='__main__':unittest.main()
