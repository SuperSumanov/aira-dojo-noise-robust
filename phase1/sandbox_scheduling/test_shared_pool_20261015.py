import unittest
from shared_pool_20261015 import State,audit
from pooling_readout_20261015 import quality,verify_queue,TASKS,ORDER


class Tests(unittest.TestCase):
    def test_fixed_waits_while_other_device_idle(self):
        s=State('fixed');s.request('0:0',0);s.request('1:0',0)
        self.assertEqual(s.admit('0:0'),0);self.assertIsNone(s.admit('1:0'))

    def test_shared_uses_idle_device(self):
        s=State('shared');s.request('0:0',0);s.request('1:0',0)
        self.assertEqual(s.admit('0:0'),0);self.assertEqual(s.admit('1:0'),1)

    def test_no_passing_global_fifo(self):
        s=State('shared');s.request('a',3);s.request('b',2)
        self.assertIsNone(s.admit('b'));self.assertEqual(s.admit('a'),0)

    def test_fixed_independent_fifo(self):
        s=State('fixed')
        for k,h in [('a',0),('b',0),('c',1)]:s.request(k,h)
        self.assertEqual(s.admit('a'),0);self.assertEqual(s.admit('c'),1)
        self.assertIsNone(s.admit('b'))

    def test_no_overcommit(self):
        s=State('shared')
        for i in range(8):s.request(str(i),i//2)
        for i in range(4):self.assertEqual(s.admit(str(i)),i)
        self.assertIsNone(s.admit('4'))
        s.release('1',True);self.assertEqual(s.admit('4'),1)

    def test_no_unsafe_release(self):
        s=State('shared');s.request('a',0);s.admit('a')
        with self.assertRaises(ValueError):s.release('a',False)
        with self.assertRaises(ValueError):s.cancel('a')

    def test_cancellation_no_retry(self):
        s=State('shared');s.request('a',0);s.cancel('a')
        with self.assertRaises(ValueError):s.request('a',0)

    def test_replay_strict(self):
        events=[dict(event='queued',key='a',home=2,device=None,queued=1,active=0),
                dict(event='admitted',key='a',home=2,device=0,queued=0,active=1),
                dict(event='released',key='a',home=2,device=0,queued=0,active=0)]
        self.assertEqual(audit(events,'shared'),dict(admissions=1,migrations=1,all_released=True))
        with self.assertRaises(ValueError):audit(events,'fixed')

    def test_duplicate_state_rejected(self):
        with self.assertRaises(ValueError):State('shared',active={'a':dict(device=0),'b':dict(device=0)})

    def fixture(self):
        return [dict(block=b,task=t,score=(.99 if k==0 else .02-(.002 if ORDER[b]=='shared' else 0)))
                for b in range(4) for k,t in enumerate(TASKS) for _ in range(4)]

    def test_quality_both_repeats(self):
        self.assertTrue(quality(self.fixture())[2])

    def test_no_pooling_rescue(self):
        rows=self.fixture()
        for r in rows:
            if r['block']==2 and r['task']==TASKS[1]:r['score']=.0201
        self.assertFalse(quality(rows)[2])

    def test_no_aerial_regression_rescue(self):
        rows=self.fixture()
        for r in rows:
            if r['block']==1 and r['task']==TASKS[0]:r['score']=.98
        self.assertFalse(quality(rows)[2])

    def test_missing_denominator_rejected(self):
        with self.assertRaises(AssertionError):quality(self.fixture()[:-1])

    def test_cpu_topology_shape(self):
        import ast
        from pathlib import Path
        tree=ast.parse(Path(__file__).with_name('pooling_trial_20261015.py').read_text(encoding='utf-8'))
        node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='cpu_slots')
        ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<fixture>','exec'),ns)
        rows=[dict(logical_cpu=i,socket=0,core=i%16) for i in range(32)]
        slots=ns['cpu_slots'](rows)
        self.assertEqual(slots,[[2*i,2*i+1] for i in range(8)])
        with self.assertRaises(ValueError):ns['cpu_slots'](rows[:8])

    def test_independent_queue_crosscheck(self):
        events=[dict(event='queued',key='a',home=2,device=None,queued=1,active=0,time=1),
                dict(event='admitted',key='a',home=2,device=0,queued=0,active=1,time=2),
                dict(event='released',key='a',home=2,device=0,queued=0,active=0,time=3)]
        self.assertEqual(verify_queue(events,'shared')['migrations'],audit(events,'shared')['migrations'])
        with self.assertRaises(AssertionError):verify_queue(events,'fixed')


if __name__=='__main__':unittest.main()
