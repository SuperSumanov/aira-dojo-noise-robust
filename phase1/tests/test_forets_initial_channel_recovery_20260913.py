import ast
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_initial_channel_recovery_20260913 import ready_before_first_dispatch,patch_sources

class Recovery(unittest.TestCase):
    def setup_case(self,first=False,second=True,dispatched=False,connect=1):
        self.time=0.;self.calls=[]
        def make(reply):
            def wait(*,timeout_seconds):
                self.calls.append(('wait',timeout_seconds));self.time+=.1 if reply else timeout_seconds
                return reply
            return SimpleNamespace(wait_for_ready=wait,stop=lambda:self.calls.append(('stop',)))
        def get(k,*,connection_timeout):
            self.calls.append(('connect',k,connection_timeout));self.time+=connect
            return make(second)
        e=SimpleNamespace(_candidate_dispatched=dispatched,_wait_timeout=120,_kernel_id='same',
            _jupyter_kernel_client=make(first),_jupyter_client=SimpleNamespace(get_kernel_client=get))
        return e
    def run_case(self,e):return ready_before_first_dispatch(e,clock=lambda:self.time)
    def test_success_no_replace(self):
        self.assertTrue(self.run_case(self.setup_case(first=True)));self.assertEqual(self.calls,[('wait',10.)])
    def test_one_replace_same_kernel_remaining(self):
        self.assertTrue(self.run_case(self.setup_case()));self.assertEqual(self.calls,[('wait',10.),('stop',),('connect','same',10.),('wait',109.)])
    def test_dead_both_total(self):
        self.assertFalse(self.run_case(self.setup_case(second=False)));self.assertEqual(self.time,120)
    def test_no_replace_after_dispatch(self):
        self.assertFalse(self.run_case(self.setup_case(dispatched=True)));self.assertEqual(self.calls,[('wait',120)])
    def test_connect_consumes_remaining(self):
        self.assertFalse(self.run_case(self.setup_case(connect=110)));self.assertEqual(len(self.calls),3)
    def test_invalid(self):
        e=self.setup_case();e._wait_timeout=float('inf')
        with self.assertRaises(ValueError):self.run_case(e)
    def test_exact_production_patch(self):
        base='35321718fef54f1907b469ab44334a30fe66b6cd:src/dojo/core/interpreters/jupyter/'
        texts=[subprocess.check_output(['git','show',base+n]).decode() for n in ('jupyter_client.py','jupyter_code_executor.py')]
        client,executor=patch_sources(*texts);ast.parse(client);ast.parse(executor)
        self.assertEqual(executor.count('ready_before_first_dispatch(self)'),1)
        self.assertEqual(executor.count('ready = self._jupyter_kernel_client.wait_for_ready'),1)
        self.assertIn('self._candidate_dispatched = True\n        result =',executor)

if __name__=='__main__':unittest.main()
