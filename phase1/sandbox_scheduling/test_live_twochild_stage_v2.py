import unittest
from live_twochild_stage_audit_v2 import counts,prove_root

ROOT=dict(operators_used=[],step=0,parents=[],is_buggy=True,code='',plan='',analysis='')
SOURCE='''class MCTS:
 def create_root_node(self):
  self.root_node=MCTSNode(code='',plan='',analysis='',is_buggy=True)
  self.journal.append(self.root_node)
'''

class VirtualRootTests(unittest.TestCase):
 def test_source_constructor(self):
  self.assertTrue(prove_root(SOURCE))
  with self.assertRaises(ValueError): prove_root(SOURCE.replace("code=''","code='candidate'"))
 def test_root_not_candidate(self):
  result=counts([ROOT,{'operators_used':['draft']},{'operators_used':['improve','analysis']}],2)
  self.assertEqual((result['virtual_root_records'],result['journal_records'],result['recorded_nodes']),(1,3,2))
  self.assertEqual(result['recorded_improves'],1)
 def test_empty_executed_program_is_still_candidate(self):
  node=dict(ROOT,operators_used=['draft'],step=1,parents=[0])
  self.assertEqual(counts([ROOT,node],2)['recorded_drafts'],1)
 def test_no_general_empty_operator_exception(self):
  for change in ({'step':1},{'parents':[0]},{'code':'x'},{'analysis':'x'},{'is_buggy':False}):
   with self.assertRaises(ValueError): counts([ROOT,dict(ROOT,**change)],2)
 def test_missing_or_duplicate_root_rejected(self):
  for nodes in ([],[ROOT,ROOT]):
   with self.assertRaises(ValueError): counts(nodes,2)

if __name__=='__main__': unittest.main()
