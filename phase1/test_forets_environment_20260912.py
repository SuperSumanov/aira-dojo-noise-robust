import copy
from pathlib import Path
import tempfile
import unittest

from forets_environment_context_20260912 import apply_context, CONTEXT
from forets_environment_build_20260912 import budget_source, derive_controller, PRIOR_COST, NEW_CAP


class EnvironmentRepairTests(unittest.TestCase):
    def config(self):
        return {'solver':{'execution_timeout':300, 'selection_policy':'uniform_random',
            'operators':{name:{'system_message_prompt_template':{'template':name}}
                for name in ('draft','improve','debug','analyze')}}}

    def test_only_three_prompts_change_and_no_in_place_mutation(self):
        original = self.config(); before = copy.deepcopy(original); changed = apply_context(original)
        self.assertEqual(original, before)
        for name in ('draft','improve','debug'):
            self.assertEqual(changed['solver']['operators'][name]['system_message_prompt_template']['template'],
                             name+'\n\n'+CONTEXT)
            changed['solver']['operators'][name] = before['solver']['operators'][name]
        self.assertEqual(changed, before)

    def test_arms_identical_after_normalizing_selector(self):
        random = self.config(); critic = self.config(); critic['solver']['selection_policy']='critic_topk_random'
        random, critic = apply_context(random), apply_context(critic)
        del random['solver']['selection_policy']; del critic['solver']['selection_policy']
        self.assertEqual(random, critic)

    def test_reject_duplicate_or_wrong_timeout(self):
        with self.assertRaises(ValueError): apply_context(apply_context(self.config()))
        config = self.config(); config['solver']['execution_timeout']=600
        with self.assertRaises(ValueError): apply_context(config)

    def budget(self):
        namespace = {}; original=Path(__file__).with_name('forets_paid_budget_20260911.py').read_text()
        exec(compile(budget_source(original), '<test-budget>', 'exec'), namespace)
        return namespace

    def test_carryover_and_new_cap_cannot_reset(self):
        b = self.budget()
        self.assertEqual(b['AUTH']['total'], PRIOR_COST+NEW_CAP)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'budget.sqlite'
            b['initialize'](path, ['a','b','c','d'])
            self.assertEqual(b['snapshot'](path)['accounted_usd'], PRIOR_COST/1e9)
            with self.assertRaises(FileExistsError): b['initialize'](path, ['a','b','c','d'])
            with self.assertRaises(b['BudgetStopped']): b['reserve'](path, 'closed_predecessor', 'bad')
            b['reserve'](path, 'a', 'a1'); b['settle'](path, 'a1', {'cost':'.7'})
            b['reserve'](path, 'b', 'b1'); b['settle'](path, 'b1', {'cost':'.7'})
            with self.assertRaises(b['BudgetStopped']): b['reserve'](path, 'c', 'c1')

    def test_unknown_charge_stops_successor(self):
        b = self.budget()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'budget.sqlite'; b['initialize'](path, ['a','b','c','d'])
            b['reserve'](path, 'a', 'a1')
            with self.assertRaises(b['BudgetStopped']): b['settle'](path, 'a1', {})
            state = b['snapshot'](path)
            self.assertTrue(state['stopped']); self.assertEqual(state['unresolved'], 1)
            self.assertEqual(state['accounted_usd'], (PRIOR_COST+700000000)/1e9)

    def test_fixed_matrix_reduction_has_no_block2(self):
        path = Path(__file__).with_name('forets_block_controller_20260911.py')
        ns = {'__name__':'forets_env_test_controller'}
        # Register for dataclasses' module lookup, using the regular loader.
        import sys, types
        module = types.ModuleType(ns['__name__']); sys.modules[module.__name__]=module
        try:
            exec(compile(derive_controller(path.name, path.read_text()), str(path), 'exec'), module.__dict__)
            order = module.expected_order()
            self.assertEqual(len(order), 4); self.assertEqual({r[2] for r in order}, {10})
            with self.assertRaises(ValueError): module.block_spec({}, 2)
        finally: del sys.modules[module.__name__]


if __name__ == '__main__': unittest.main()
