"""CPU-only POSIX signal reproduction of18510; frozen GPU sources stay intact.

The candidate uses the existing10/12 transaction guard only inside fixtures.
No production scheduling code, timing budget, or historical artifact is edited.
"""
import contextlib
import hashlib
import json
from pathlib import Path
import signal
import tempfile
import threading
import unittest
from unittest.mock import patch

import shared_pool_20261015 as pool
from deferred_alarm_transaction_20261012 import protect

class Expired(BaseException):pass
def expire(*args):raise Expired()

@unittest.skipUnless(hasattr(signal,'pthread_sigmask'),'Requires real POSIX thread signal delivery')
class SignalAtomicityTests(unittest.TestCase):
    def setUp(self):
        self.old=signal.signal(signal.SIGALRM,expire)
    def tearDown(self):
        signal.signal(signal.SIGALRM,self.old)

    @staticmethod
    def deliver():
        # A different thread may receive the OS signal even when the main
        # thread masks it; Python still dispatches the handler on main.
        def sender():
            signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGALRM})
            signal.raise_signal(signal.SIGALRM)
        t=threading.Thread(target=sender);t.start();t.join()

    @contextlib.contextmanager
    def inject_at_replace(self,ordinal):
        original=pool.os.replace;counter=[0]
        def replacing(src,dst):
            counter[0]+=1
            if counter[0]==ordinal:self.deliver()
            return original(src,dst)
        with patch.object(pool.os,'replace',replacing):yield

    @staticmethod
    def events(root):
        return [json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]

    def test_unsafe_acquire_reproduces_orphan_and_secondary_file_exists(self):
        with tempfile.TemporaryDirectory(prefix='pool-alarm-repro-') as td:
            root=Path(td)/'pool';pool.initialize(root,'shared')
            lease=pool.Lease(root,'11:0',lambda:None,lambda *a,**k:None)
            with self.inject_at_replace(2),self.assertRaises(FileExistsError):
                lease.acquire()
            self.assertEqual(len(list(root.glob('.state-*'))),1)
            with self.assertRaises(ValueError):pool.audit(self.events(root),'shared')

    def test_guarded_acquire_commits_then_expires_and_releases(self):
        original=pool.locked
        for mode in ('fixed','shared'):
            for repeat in range(20):
                with self.subTest(mode=mode,repeat=repeat),tempfile.TemporaryDirectory(prefix='pool-alarm-fixed-') as td:
                    root=Path(td)/'pool';pool.initialize(root,mode)
                    lease=pool.Lease(root,'11:0',lambda:None,lambda *a,**k:None)
                    with patch.object(pool,'locked',protect(original)):
                        with self.inject_at_replace(2),self.assertRaises(Expired):lease.acquire()
                        self.assertTrue(lease.held)
                        lease.release(cleanup_verified=True)
                    self.assertEqual(list(root.glob('.state-*')),[])
                    state=json.loads((root/'state.json').read_text())
                    self.assertEqual(state['active'],{});self.assertEqual(state['queue'],[])
                    self.assertTrue(pool.audit(self.events(root),mode)['all_released'])

    def test_guarded_queued_cancellation_commits_before_expiry(self):
        original=pool.locked
        with tempfile.TemporaryDirectory(prefix='pool-alarm-cancel-') as td:
            root=Path(td)/'pool';pool.initialize(root,'shared')
            def deadline():raise Expired()
            lease=pool.Lease(root,'11:0',deadline,lambda *a,**k:None)
            with patch.object(pool,'locked',protect(original)):
                with self.inject_at_replace(2),self.assertRaises(Expired):lease.acquire()
            self.assertFalse(lease.held)
            self.assertEqual(list(root.glob('.state-*')),[])
            self.assertTrue(pool.audit(self.events(root),'shared')['all_released'])

    def test_guarded_release_commits_before_expiry(self):
        original=pool.locked
        with tempfile.TemporaryDirectory(prefix='pool-alarm-release-') as td:
            root=Path(td)/'pool';pool.initialize(root,'shared')
            lease=pool.Lease(root,'11:0',lambda:None,lambda *a,**k:None)
            with patch.object(pool,'locked',protect(original)):
                lease.acquire()
                with self.inject_at_replace(1),self.assertRaises(Expired):lease.release(cleanup_verified=True)
            self.assertEqual(list(root.glob('.state-*')),[])
            self.assertTrue(pool.audit(self.events(root),'shared')['all_released'])

    def test_frozen_gpu_queue_source_unchanged(self):
        path=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v2/shared_pool_20261015.py')
        if not path.exists():self.skipTest('Frozen remote source not mounted')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'5b0ba152a80c39af7e0a8465a013203fcddb65c7937a5ff9e0a96661ff302512')

if __name__=='__main__':unittest.main(verbosity=2)
