import ast
from pathlib import Path
import unittest
from forets_environment_build_20260912 import budget_source as environment_budget, derive_controller
from forets_review_build_20260912 import order,budget_source,derive,ACCOUNTED,INCREMENT


class ReviewBuildTests(unittest.TestCase):
    def test_seed_order_matches_controller(self):
        name='forets_block_controller_20260911.py'
        source=derive(name,derive_controller(name,Path(__file__).with_name(name).read_text()))
        fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='expected_order')
        ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<order>','exec'),ns)
        self.assertEqual(ns['expected_order'](),tuple((1,task,11,arm) for task,arm in order()))
        self.assertEqual([arm for task,arm in order()],['critic_topk_random','uniform_random','uniform_random','critic_topk_random'])

    def test_budget_keeps_reservation_and_disables_initialization(self):
        original=Path(__file__).with_name('forets_paid_budget_20260911.py').read_text()
        ns={};exec(compile(budget_source(environment_budget(original)),'<budget>','exec'),ns)
        self.assertEqual(ns['AUTH']['total'],ACCOUNTED+INCREMENT)
        self.assertEqual(ns['AUTH']['run_limit'],1500000000)
        self.assertEqual(ns['RESERVE'],700000000)
        self.assertLess(ns['AUTH']['total'],10_000_000_000)
        with self.assertRaises(RuntimeError):ns['initialize']('unused',[])

    def test_route_separates_old_unknown_from_new_failures(self):
        name='forets_paid_route_20260911.py'
        result=derive(name,Path(__file__).with_name(name).read_text())
        ast.parse(result)
        self.assertIn("FORETS_PAID_SCOPE='route_s11'",result)
        self.assertIn('unknown_ids()!=prior_unknown',result)


if __name__=='__main__':unittest.main()
