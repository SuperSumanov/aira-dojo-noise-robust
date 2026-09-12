import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('ready',Path(__file__).parents[1]/'forets_kernel_readiness_20260912.py')
ready=importlib.util.module_from_spec(spec);spec.loader.exec_module(ready)


class Fake:
    def __init__(self, scenario):self.now=0.;self.sent=[];self.pending=[];self.scenario=scenario
    def clock(self):return self.now
    def _send_message(self,**kwargs):
        assert kwargs==dict(content={},channel='shell',message_type='kernel_info_request')
        ident=str(len(self.sent));self.sent.append(ident)
        self.pending.extend(self.scenario(ident))
        return ident
    def _receive_message(self,timeout):
        if self.pending:self.now+=.01;return self.pending.pop(0)
        self.now+=timeout;return None


def pair(ident):
    return [dict(parent_header=dict(msg_id=ident),msg_type='kernel_info_reply'),
            dict(parent_header=dict(msg_id=ident),msg_type='status',content=dict(execution_state='idle'))]


class ReadinessTests(unittest.TestCase):
    def test_first_request_lost(self):
        c=Fake(lambda n:pair(n) if n=='1' else [])
        self.assertTrue(ready.wait_for_ready(c,5,clock=c.clock));self.assertEqual(len(c.sent),2)
    def test_delayed_old_reply_is_valid(self):
        c=Fake(lambda n:pair('0') if n=='1' else [])
        self.assertTrue(ready.wait_for_ready(c,5,clock=c.clock))
    def test_no_response_deadline(self):
        c=Fake(lambda n:[])
        self.assertFalse(ready.wait_for_ready(c,3,clock=c.clock));self.assertEqual(c.now,3)
    def test_unrelated_traffic_does_not_extend_deadline(self):
        c=Fake(lambda n:pair('unrelated')*100)
        self.assertFalse(ready.wait_for_ready(c,3,clock=c.clock));self.assertLessEqual(c.now,3.02)
    def test_shell_reply_alone_insufficient(self):
        c=Fake(lambda n:pair(n)[:1]);self.assertFalse(ready.wait_for_ready(c,3,clock=c.clock))
    def test_idle_before_shell(self):
        c=Fake(lambda n:pair(n)[::-1]);self.assertTrue(ready.wait_for_ready(c,3,clock=c.clock))
    def test_do_not_mix_requests(self):
        c=Fake(lambda n:pair('0')[:1]+pair('1')[1:]);self.assertFalse(ready.wait_for_ready(c,3,clock=c.clock))
    def test_invalid_deadlines(self):
        for value in [0,-1,float('nan'),float('inf'),True,'3']:
            with self.subTest(value=value),self.assertRaises(ValueError):ready.wait_for_ready(Fake(lambda n:[]),value)


if __name__=='__main__':unittest.main()
