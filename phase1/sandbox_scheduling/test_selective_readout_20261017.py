import unittest
from selective_readout_20261017 import quality,ORDER,TASKS


class Tests(unittest.TestCase):
    def rows(self):return [dict(block=b,task=t,score=.99 if k==0 else .02-(.002 if m=='selective' else 0)) for b,m in enumerate(ORDER) for k,t in enumerate(TASKS) for _ in range(4)]
    def test_two_complete_comparisons(self):
        by,cs,gate=quality(self.rows());self.assertEqual(len(by),8);self.assertEqual(len(cs),4);self.assertTrue(gate)
    def test_missing_row(self):
        with self.assertRaises(AssertionError):quality(self.rows()[:-1])
    def test_missing_score(self):
        rows=self.rows();rows[0]['score']=None
        with self.assertRaises(AssertionError):quality(rows)
    def test_no_repeat_rescue(self):
        rows=self.rows()
        for r in rows:
            if r['block']==2 and r['task']==TASKS[1]:r['score']=.02
        self.assertFalse(quality(rows)[2])
    def test_no_task_rescue(self):
        rows=self.rows()
        for r in rows:
            if r['block']==1 and r['task']==TASKS[0]:r['score']=.98
        self.assertFalse(quality(rows)[2])


if __name__=='__main__':unittest.main()
