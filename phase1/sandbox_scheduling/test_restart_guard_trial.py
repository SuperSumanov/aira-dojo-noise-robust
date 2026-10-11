import collections,unittest
import restart_guard_trial_20261011 as c

class Tests(unittest.TestCase):
    def test_fixed_balanced_matrix(self):
        rows=c.schedule();self.assertEqual(len(rows),12)
        self.assertEqual(collections.Counter((r['arm'],r['case']) for r in rows),{(a,b):3 for a in ('old','guard') for b in ('normal','exit')})
        self.assertEqual([r['index'] for r in rows],list(range(12)))
    def test_only_tiny_predeclared_programs(self):
        self.assertEqual(c.CODES['normal'],"print('R14_NORMAL_OK')")
        self.assertEqual(c.CODES['exit'],"import os,time\ntime.sleep(1)\nos._exit(17)")
        self.assertEqual(c.SITE.count('import kernel_lifecycle_observer'),1)

if __name__=='__main__':unittest.main()
