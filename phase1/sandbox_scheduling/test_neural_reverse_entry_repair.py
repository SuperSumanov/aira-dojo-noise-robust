import ast
import unittest
from unittest.mock import patch
import neural_reverse_entry_repair_20261010 as repair

ACCOUNT='17364|COMPLETED|216|gres/gpu=1\n17366|COMPLETED|1796|gres/gpu=1\n17368|COMPLETED|9204|gres/gpu=3\n17376|FAILED|63|gres/gpu=1\n'

class EntryRepairTests(unittest.TestCase):
 def test_exact_generated_wrapper_import(self):
  scope={}
  exec('from neural_reverse_entry_repair_20261010 import configure',scope)
  sentinel=object()
  with patch.object(repair.old.e,'configure',return_value=sentinel):
   self.assertIs(scope['configure'](),sentinel)
 def test_delegation_does_not_rewrite_worker(self):
  with patch.object(repair.old.e,'configure',return_value='unchanged') as target:
   self.assertEqual(repair.configure(),'unchanged');target.assert_called_once_with()
 def test_failure_cost_retained(self):
  costs=repair.accounted_costs(ACCOUNT)
  self.assertEqual(costs['17376'],63)
  self.assertEqual(sum(costs.values())+repair.old.CAP,34187)
 def test_missing_or_nonterminal_failure_rejected(self):
  for text in (ACCOUNT.rsplit('17376',1)[0],ACCOUNT.replace('17376|FAILED','17376|RUNNING')):
   with self.assertRaises(ValueError): repair.accounted_costs(text)
 def test_all_costs_bounded(self):
  with self.assertRaises(ValueError): repair.accounted_costs(ACCOUNT.replace('FAILED|63','FAILED|5000'))
 def test_scope_separate_and_limits_unchanged(self):
  self.assertNotEqual(repair.FAILED,repair.old.e.R)
  self.assertEqual(repair.old.CAP,4500)
  rows=repair.old.reverse_schedule()
  self.assertEqual(len(rows),12)
  self.assertEqual([r['arm'] for r in rows[::2]],['share2','pipeline','pipeline','share2','share2','pipeline'])

if __name__=='__main__': unittest.main()
