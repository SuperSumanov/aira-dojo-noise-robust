import unittest
import execution_guarded_six_20261011 as c
class Tests(unittest.TestCase):
    def test_fixed_schedule_and_all_roots(self):
        c.activate();rows=c.e.schedule()
        self.assertEqual(len(rows),14)
        self.assertEqual([sum(r['block']==b for r in rows) for b in range(4)],[1,1,6,6])
        self.assertEqual({r['program'] for r in rows},{1})
        for mod in (c.g,c.g.s,c.g.m,c.e,c.e.r,c.e.r.s,c.e.r.s.d):
            self.assertEqual(mod.ROOT,c.ROOT);self.assertEqual(mod.NAME,c.NAME)
    def test_unchanged_actual_worker_and_controller(self):
        import inspect
        self.assertIn('return m.worker(index)',inspect.getsource(c.g.worker))
        self.assertNotIn('stack_executor',inspect.getsource(c.g.worker))
        self.assertIn('range(4)',inspect.getsource(c.e.controller))
if __name__=='__main__':unittest.main()
