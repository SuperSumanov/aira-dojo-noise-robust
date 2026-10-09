import unittest
from opportunity_recheck_20261010 import schedule,summarize


class RecheckTests(unittest.TestCase):
    def fixture(self):
        rows=[dict(**r,status='complete',grounded=True,score=.5+.02*(r['role']=='child')*(r['pair']==0)) for r in schedule()]
        programs=[dict(original_score=x) for x in (.5,.52,.6,.6)]
        return rows,programs
    def test_complete(self):
        r=summarize(*self.fixture())
        self.assertEqual(r['pairs'][0]['new_deltas'],['0.02','0.02'])
        self.assertTrue(r['pairs'][0]['both_positive'])
        self.assertFalse(r['pairs'][1]['both_positive'])
    def test_missing_not_imputed(self):
        rows,p=self.fixture();rows[0]['status']='failed'
        r=summarize(rows,p);self.assertEqual(r['pairs'][0]['new_deltas'],[None,'0.02'])
        self.assertFalse(r['pairs'][0]['both_positive']);self.assertIsNone(r['pairs'][0]['median'])
    def test_grounding_required(self):
        rows,p=self.fixture();rows[0]['grounded']=False
        self.assertFalse(summarize(rows,p)['pairs'][0]['both_positive'])
    def test_order_and_full_denominator(self):
        rows,p=self.fixture()
        for bad in (rows[:-1],rows[::-1]):
            with self.assertRaises(ValueError):summarize(bad,p)
    def test_nonfinite_and_bool(self):
        for value in (float('nan'),float('inf'),True):
            rows,p=self.fixture();rows[0]['score']=value
            self.assertFalse(summarize(rows,p)['pairs'][0]['both_positive'])
    def test_counterbalanced_roles_fixed_program(self):
        rows=schedule();self.assertEqual([r['index'] for r in rows],list(range(8)))
        self.assertEqual([r['role'] for r in rows[:2]],['parent','child'])
        self.assertEqual([r['role'] for r in rows[4:6]],['child','parent'])
        self.assertEqual([sum(r['program']==p for r in rows) for p in range(4)],[2]*4)


if __name__=='__main__':unittest.main()
