import copy,math,unittest
from run_comparison_complete_pool_order_20260920 import select_pair,schedule
from readout_comparison_complete_pool_order_20260920 import audit_actions

class Order(unittest.TestCase):
    def setUp(self):
        self.programs=[dict(slot=i,code_sha256=str(i)) for i in range(6)]
        self.selection=select_pair(self.programs,{i:6.-i for i in range(6)},5)
    def test_same_full_action_set(self):
        a=schedule(self.selection,False);b=schedule(self.selection,True)
        self.assertEqual(sorted(a),sorted(b));self.assertNotEqual(a,b)
        self.assertEqual(len(a),8)
    def test_determinism_and_ties(self):
        for seed in (5,6):
            a=select_pair(self.programs,{i:0. for i in range(6)},seed)
            self.assertEqual(a,select_pair(self.programs,{i:0. for i in range(6)},seed));self.assertEqual(a['critic_order'],list(range(6)))
    def test_invalid_scores(self):
        for scores in ({i:0. for i in range(5)},{i:math.nan for i in range(6)}):
            with self.assertRaises(ValueError):select_pair(self.programs,scores,5)
    def test_real_incumbent_not_oracle(self):
        seq=schedule(self.selection,True);actions=[]
        for kind,slot in seq[:6]:
            actions.append(dict(kind=kind,slot=slot,depth=0,code_sha256=str(slot),submission_sha256='f',exit_code=0,timed_out=False,native_accepted=True,internal_metric=.7,completed_seconds=1.))
        inc=dict(action_index=0,internal_metric=.7,code_sha256=str(seq[0][1]),submission_sha256='f',accepted_seconds=1.)
        out=audit_actions(actions,self.selection,{p['slot']:p for p in self.programs},True,inc);self.assertEqual(out['initial_programs_executed'],6)
        wrong=inc|dict(action_index=1)
        with self.assertRaises(ValueError):audit_actions(actions,self.selection,{p['slot']:p for p in self.programs},True,wrong)
    def test_order_violation(self):
        actions=[dict(kind='execute',slot=s,depth=0,code_sha256=str(s),native_accepted=False) for s in reversed(self.selection['chosen'])]
        with self.assertRaises(ValueError):audit_actions(actions,self.selection,{p['slot']:p for p in self.programs},True,None)
    def test_unknown_prefix_allowed_not_imputed(self):
        slot=self.selection['chosen'][0];actions=[dict(kind='execute',slot=slot,depth=0,status='unknown')]
        out=audit_actions(actions,self.selection,{p['slot']:p for p in self.programs},False,None);self.assertEqual(out['native_accepted_actions'],0)

if __name__=='__main__':unittest.main()
