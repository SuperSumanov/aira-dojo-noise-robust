import copy
import unittest
import forets_scope_preservation_20260914 as p

class Tests(unittest.TestCase):
    def test_frozen_balanced_order(self):
        rows=p.order();self.assertEqual(len(rows),12)
        self.assertEqual(len(set(rows)),12)
        for task in p.TASKS:
            for seed in p.SEEDS:
                arms=[r[3] for r in rows if r[1:3]==(task,seed)]
                self.assertEqual(set(arms),set(p.ARMS))

    def test_only_instructions_and_interface(self):
        base={'solver':{'operators':{op:{'system_message_prompt_template':{'template':'unchanged original '+op},'temperature':1} for op in ('draft','improve','debug')},
            'num_children':2,'num_children_to_choose':2,'time_limit_secs':1200,'execution_timeout':300,'use_test_score':False}}
        for arm in p.ARMS:
            result=p.transform(base,arm)
            self.assertEqual(p.strip_intervention(result,arm),base)
        self.assertNotIn('edit_scope',base['solver'])

    def test_no_accidental_double_intervention(self):
        base={'solver':{'operators':{op:{'system_message_prompt_template':{'template':'base'}} for op in ('draft','improve','debug')}}}
        for arm in ('preserve_program','model_module'):
            with self.assertRaises(ValueError):p.transform(p.transform(base,arm),arm)

if __name__=='__main__':unittest.main()
