from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit_forets_chain_geometry_20260913 import geometry
from forets_incumbent_parent_reference_20260913 import incumbent_path


class ParentTests(unittest.TestCase):
    def test_saved_chain_vs_branch(self):
        nodes=[dict(id='r',step=0,parents=[],children=[1]),dict(id='a',step=1,parents=[0],children=[2]),dict(id='b',step=2,parents=[1],children=[])]
        self.assertEqual(geometry(nodes)['branching_nodes'],0)
        self.assertEqual(geometry(nodes)['unreachable_saved_nodes'],0)
        self.assertEqual(geometry(nodes)['unpersisted_child_references'],0)
        nodes[0]['children'].append(2);nodes[1]['children']=[];nodes[2]['parents']=[0]
        self.assertEqual(geometry(nodes)['branching_nodes'],1)
    def test_uuid_edge_cannot_masquerade_as_step(self):
        with self.assertRaises(ValueError):geometry([dict(id='r',step=0,parents=[],children=['r'])])
    def test_reference_returns_nonleaf_incumbent_without_external_scores(self):
        root=NS(parents=[],is_buggy=True);valid=NS(parents=[root],is_buggy=False)
        bad=NS(parents=[valid],is_buggy=True);valid.children=[bad]
        self.assertEqual(incumbent_path(root,NS(get_best_node=lambda:valid)),[root,valid])
        self.assertEqual(incumbent_path(root,NS(get_best_node=lambda:None)),[root])
    def test_invalid_journal_fails_closed(self):
        root=NS(parents=[],is_buggy=True)
        for node in (NS(parents=[root],is_buggy=True),NS(parents=[],is_buggy=False)):
            with self.assertRaises(ValueError):incumbent_path(root,NS(get_best_node=lambda:node))


if __name__=='__main__':unittest.main()
