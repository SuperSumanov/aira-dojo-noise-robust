import unittest
from diverse_readout_20261017 import quality,ORDER,TASKS


class Tests(unittest.TestCase):
    def fixture(self):
        return [dict(block=b,task=t,score=(.99 if k==0 else .02-(.002 if mode=='diverse' else 0)))
            for b,mode in enumerate(ORDER) for k,t in enumerate(TASKS) for _ in range(4)]
    def test_all_controls_both_repeats(self):
        blocks,contrasts,gate=quality(self.fixture())
        self.assertEqual(len(blocks),12);self.assertEqual(len(contrasts),8);self.assertTrue(gate)
    def test_no_single_control_rescue(self):
        rows=self.fixture()
        for r in rows:
            if r['block']==1 and r['task']==TASKS[1]:r['score']=.017
        self.assertFalse(quality(rows)[2])
    def test_no_one_repeat_rescue(self):
        rows=self.fixture()
        for r in rows:
            if r['block']==3 and r['task']==TASKS[1]:r['score']=.0201
        self.assertFalse(quality(rows)[2])
    def test_no_task_rescue(self):
        rows=self.fixture()
        for r in rows:
            if r['block']==2 and r['task']==TASKS[0]:r['score']=.98
        self.assertFalse(quality(rows)[2])
    def test_full_denominator(self):
        with self.assertRaises(AssertionError):quality(self.fixture()[:-1])
    def test_nonfinite_rejected(self):
        rows=self.fixture();rows[0]['score']=float('nan')
        with self.assertRaises(AssertionError):quality(rows)


if __name__=='__main__':unittest.main()
