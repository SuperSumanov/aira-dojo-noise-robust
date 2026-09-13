import unittest
import compare_scope_classic_20260914 as c

def fixture():
    return [dict(task=t,seed=s,arm=a,technical_eligible=True,action_valid=True,
        action_score=.5 if a=='whole_program' else (.4 if t==c.TASKS[0] else .6)) for t in c.TASKS for s in c.SEEDS for a in c.ARMS]

class Tests(unittest.TestCase):
    def test_frozen_gate(self):
        r=c.scope_summary(fixture());self.assertTrue(r['original_development_gate']);self.assertEqual(r['observed_wins'],8)
        self.assertEqual(r['net_win_missingness_sensitivity'],[8,8])
    def test_missing_and_no_compensating_imbalance(self):
        rows=fixture();rows[0]['technical_eligible']=False;rows[2]['technical_eligible']=False
        r=c.scope_summary(rows);self.assertFalse(r['original_development_gate']);self.assertEqual(r['unknown_pairs'],2)
        self.assertEqual(r['net_win_missingness_sensitivity'],[4,8])
    def test_one_task_cannot_carry_other(self):
        rows=fixture()
        for r in rows:
            if r['task']==c.TASKS[1]:r['action_score']=.5
        self.assertFalse(c.scope_summary(rows)['original_development_gate'])
    def test_descriptive_interval(self):
        r=c.describe([1,1,1,1]);self.assertEqual(r['bootstrap_mean_95'],[1,1])
        self.assertEqual(c.percentile([0,10],.25),2.5)
    def test_complete_denominator(self):
        for rows in (fixture()[:-1],fixture()[:-1]+[fixture()[0]]):
            with self.assertRaises(ValueError):c.scope_summary(rows)
    def test_strong_reference_gate(self):
        classic=[dict(task=t,seed=s,valid=True,status='completed',score=.5) for t in c.TASKS for s in c.SEEDS]
        self.assertTrue(c.reference_summary(fixture(),classic)['successor_reference_gate'])
        for r in classic:r['score']=.1 if r['task']==c.TASKS[0] else .9
        self.assertFalse(c.reference_summary(fixture(),classic)['successor_reference_gate'])
    def test_reference_missingness_is_not_a_win(self):
        classic=[dict(task=t,seed=s,valid=True,status='completed',score=.5) for t in c.TASKS for s in c.SEEDS]
        for r in classic[:2]:r.update(valid=None,status='infrastructure_error',score=None)
        out=c.reference_summary(fixture(),classic)
        self.assertFalse(out['successor_reference_gate'])
        self.assertEqual(sum(g['unknown_pairs'] for g in out['groups'] if g['arm']=='model_module'),2)

if __name__=='__main__':unittest.main()
