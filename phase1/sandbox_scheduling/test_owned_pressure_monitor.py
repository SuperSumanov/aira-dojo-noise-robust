import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import owned_pressure_monitor as m


class Clock:
    def __init__(self): self.now=0.0
    def monotonic(self): return self.now
    def sleep(self,n): self.now+=n

def sample(start=1,stable=True):
    return dict(root_pid=99,root_start_ticks=start,root_identity_stable=stable,
                owned_descendants=[dict(pid=99,state='S')])


class Tests(unittest.TestCase):
    def test_bounded_exclusive_and_private(self):
        clock=Clock()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'numeric.jsonl'
            result=m.monitor(99,out,3,1,lambda _:sample(),clock.monotonic,clock.sleep)
            self.assertEqual(result['samples'],3)
            self.assertEqual(result['reason'],'duration_limit')
            self.assertEqual(out.stat().st_mode & 0o777,0o600)
            before=out.read_bytes()
            with self.assertRaises(FileExistsError):
                m.monitor(99,out,3,1,lambda _:sample(),clock.monotonic,clock.sleep)
            self.assertEqual(before,out.read_bytes())

    def test_pid_reuse_stops_before_exporting_new_identity(self):
        clock=Clock();values=iter([sample(),sample(start=2)])
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'numeric.jsonl'
            result=m.monitor(99,out,5,1,lambda _:next(values),clock.monotonic,clock.sleep)
            self.assertEqual(result['reason'],'root_identity_changed')
            self.assertEqual(result['samples'],1)
            self.assertNotIn('"root_start_ticks": 2',out.read_text())

    def test_initial_unstable_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'numeric.jsonl'
            with self.assertRaises(ProcessLookupError):m.monitor(99,out,snapshot=lambda _:sample(stable=False))
            self.assertFalse(out.exists())

    def test_zombie_is_not_a_live_worker(self):
        clock=Clock();value=sample();value['owned_descendants'][0]['state']='Z'
        with tempfile.TemporaryDirectory() as tmp:
            result=m.monitor(99,Path(tmp)/'numeric.jsonl',5,1,lambda _:value,clock.monotonic,clock.sleep)
            self.assertEqual(result['reason'],'root_exited')
            self.assertEqual(result['samples'],0)

    def test_disappeared_and_permission_denied_are_distinct(self):
        for error,reason in [(FileNotFoundError(),'root_exited_or_changed'),(PermissionError(),'observation_failed_closed')]:
            clock=Clock();calls=0
            def snap(_):
                nonlocal calls
                calls+=1
                if calls>1:raise error
                return sample()
            with tempfile.TemporaryDirectory() as tmp:
                result=m.monitor(99,Path(tmp)/'numeric.jsonl',5,1,snap,clock.monotonic,clock.sleep)
                self.assertEqual(result['reason'],reason)
                self.assertEqual(result['samples'],1)

    @unittest.skipUnless(sys.platform.startswith('linux'),'Linux/proc only')
    def test_real_owned_child_lifecycle(self):
        proc=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(1.6)'])
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out=Path(tmp)/'numeric.jsonl'
                result=m.monitor(proc.pid,out,4,1)
                records=[json.loads(x) for x in out.read_text().splitlines()]
                self.assertGreaterEqual(result['samples'],1)
                self.assertIn(result['reason'],('root_exited','root_exited_or_changed'))
                self.assertLess(result['elapsed_seconds'],4)
                for record in records:
                    if record['event']!='sample':continue
                    self.assertTrue(record['value']['root_identity_stable'])
                    self.assertIn('target_cgroups',record['value'])
                    self.assertIn('observer',record['value']['scope_note'])
                    self.assertTrue(any(proc.pid in g['members'] for g in record['value']['target_cgroups']['groups']))
                    self.assertTrue(all(p['uid']==os.getuid() for p in record['value']['owned_descendants']))
                    for process in record['value']['owned_descendants']:
                        self.assertFalse({'cmdline','environ','command','code','labels'} & process.keys())
        finally:
            if proc.poll() is None:proc.terminate()
            proc.wait(timeout=5)


if __name__=='__main__':unittest.main()
