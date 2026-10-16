import unittest
from clock_rank_readout_20261016 import ranking

class Ranking(unittest.TestCase):
    def fixture(self):
        return [dict(program=p,block=b,mode=('solo','colocated','colocated','solo')[b],complete=True,valid=True,
          score=(.9 if p%2==0 else .8) if b in (0,3) else (.7 if p%2==0 else .8)) for b in range(4) for p in range(4)]
    def test_both_tasks_direction(self):
        r=ranking(self.fixture())
        self.assertTrue(all(x['strict_repeated_flip'] for x in r))
        self.assertEqual(r[0]['interval_separated_order'],dict(solo=1,colocated=-1))
        self.assertEqual(r[1]['interval_separated_order'],dict(solo=-1,colocated=1))
    def test_one_repeat_not_enough(self):
        r=self.fixture();r[8]['score']=.95
        self.assertFalse(ranking(r)[0]['strict_repeated_flip'])
    def test_tie_is_not_flip(self):
        r=self.fixture();r[4]['score']=.8
        self.assertFalse(ranking(r)[0]['strict_repeated_flip'])
    def test_failure_keeps_task_incomplete(self):
        r=self.fixture();r[0]['complete']=False
        self.assertEqual(ranking(r)[0],dict(task_index=0,complete=False))

if __name__=='__main__':unittest.main()
