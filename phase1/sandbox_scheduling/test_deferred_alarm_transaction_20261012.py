import json,signal,tempfile,threading,unittest
from pathlib import Path
from deferred_alarm_transaction_20261012 import protect,defer_alarm
import live_admission as la

class Expired(BaseException):pass
def expire(*args):raise Expired()

class AlarmTests(unittest.TestCase):
    def setUp(self):self.old=signal.signal(signal.SIGALRM,expire)
    def tearDown(self):signal.signal(signal.SIGALRM,self.old)
    def test_other_thread_delivery_commits_before_expiry(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'queue';la.initialize(d,1)
            for i in range(20):
                with self.assertRaises(Expired):
                    with protect(la.locked)(d) as state:
                        state.request(str(i))
                        def deliver():
                            signal.pthread_sigmask(signal.SIG_UNBLOCK,{signal.SIGALRM})
                            signal.raise_signal(signal.SIGALRM)
                        t=threading.Thread(target=deliver);t.start();t.join()
                        state.admit(str(i));state.finish(str(i),cleanup_verified=True)
                value=json.loads((d/'state.json').read_text())
                self.assertEqual(value['finished'],[str(x) for x in range(i+1)])
                self.assertFalse(list(d.glob('*.tmp')))
    def test_nested_deferral(self):
        events=[]
        with self.assertRaises(Expired):
            with defer_alarm():
                with defer_alarm():signal.raise_signal(signal.SIGALRM)
                events.append('inner committed')
            events.append('unreachable')
        self.assertEqual(events,['inner committed'])
    def test_non_signal_failure_rolls_back(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'queue';la.initialize(d,1)
            with self.assertRaises(ValueError):
                with protect(la.locked)(d) as state:
                    state.request('x');raise ValueError('injected')
            self.assertEqual(json.loads((d/'state.json').read_text())['queue'],[])
    def test_success_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'queue';la.initialize(d,1)
            with protect(la.locked)(d) as state:state.request('x')
            self.assertEqual(json.loads((d/'state.json').read_text())['queue'],['x'])

if __name__=='__main__':unittest.main()
