import unittest
import numpy as np
from cheap_leave_task_out_20260914 import fold_indices,run_weights,metrics
class TestFolds(unittest.TestCase):
    def test_purge_any_identity_and_all_task_runs(self):
        rows=[dict(task='a',run='a1'),dict(task='a',run='a2')]+[dict(task='b',run='b1')]*4
        keys=[('a','b','c'),('d','e','f'),('a','x','y'),('w','e','z'),('u','v','c'),('m','n','o')]
        self.assertEqual(fold_indices(rows,keys,'a'),([5],[0,1],3))
    def test_equal_run_mass(self):
        w=run_weights([{'run':'a'},{'run':'a'},{'run':'b'}])
        self.assertAlmostEqual(sum(w[:2]),w[2]);self.assertAlmostEqual(sum(w),3)
    def test_within_run_and_undefined(self):
        r=metrics([dict(run='a',label=0),dict(run='a',label=1),dict(run='b',label=1)],[1,1,0])
        self.assertEqual((r['within_run_mean_auc'],r['defined_runs'],r['total_runs']),(.5,1,2))
        self.assertIsNone(r['per_run'][1]['auc'])
    def test_node_and_run_weighted_different(self):
        rows=[dict(run='a',label=0),dict(run='a',label=1),dict(run='a',label=1),dict(run='b',label=0),dict(run='b',label=1)]
        r=metrics(rows,[0,1,1,2,0])
        self.assertNotEqual(r['node_auc'],r['run_weighted_task_auc'])
if __name__=='__main__':unittest.main()
