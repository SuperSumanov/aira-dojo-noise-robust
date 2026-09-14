import copy,unittest
import readout_cheap_selector_20260914 as r
def fixture():return [dict(task=t,seed=s,arm=a,technical_eligible=True,action_valid=True,iteration_valid=True,action_score=.5,iteration_score=.5) for t in r.TASKS for s in r.SEEDS for a in r.ARMS]
class Tests(unittest.TestCase):
    def test_ties_do_not_pass(self):
        out=r.comparisons(fixture());self.assertFalse(out['investment_gate']);self.assertEqual(len(out['pairs']),16)
        self.assertTrue(all(g['ties']==2 for g in out['groups']))
    def test_oriented_improvement(self):
        rows=fixture()
        for x in rows:
            if x['arm']=='learned_validity':x['action_score']=.4 if x['task']==r.TASKS[0] else .6
        out=r.comparisons(rows);self.assertTrue(out['investment_gate']);self.assertTrue(all(g['wins']==2 for g in out['groups'] if g['endpoint']=='action'))
    def test_unknown_is_not_loss_or_zero(self):
        rows=fixture();rows[0]['technical_eligible']=False;out=r.comparisons(rows)
        self.assertFalse(out['investment_gate']);self.assertIsNone(out['pairs'][0]['gain']);self.assertIsNone(out['pairs'][0]['sign'])
    def test_one_invalid(self):
        rows=fixture();rows[0].update(action_valid=False,action_score=None);out=r.comparisons(rows)
        self.assertEqual(out['pairs'][0]['sign'],1);self.assertIsNone(out['pairs'][0]['gain'])
    def test_both_invalid(self):
        rows=fixture()
        for x in rows[:3]:x.update(action_valid=False,action_score=None)
        self.assertEqual(r.comparisons(rows)['pairs'][0]['sign'],0)
    def test_coverage_types_finiteness(self):
        for rows in (fixture()[:-1],fixture()[:-1]+[fixture()[0]]):
            with self.assertRaises(ValueError):r.comparisons(rows)
        for bad in (None,float('nan'),True):
            rows=fixture();rows[0]['action_score']=bad
            with self.assertRaises(ValueError):r.comparisons(rows)
    def test_strong_control_required(self):
        rows=fixture()
        for x in rows:
            if x['arm']!='uniform':x['action_score']=.4 if x['task']==r.TASKS[0] else .6
        self.assertFalse(r.comparisons(rows)['investment_gate'])
if __name__=='__main__':unittest.main()
