from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_forets_reference_records_20260913 import expected_references


def n(step,value,*,bug=False):
    return dict(id=str(step),step=step,code='code'+str(step),exec_time=1.,exit_code=0,is_buggy=bug,
        metric=dict(value=value,maximize=False,info={'hidden_external_grade':999}),parents=[0])


class ReplayTests(unittest.TestCase):
    def test_future_excluded_and_tie_uses_first(self):
        rows=expected_references([n(1,.5),n(2,.5),n(3,.6),n(4,.1)],'2',4)
        self.assertEqual([r['step'] for r in rows],[2,1,3])
        self.assertNotIn('hidden_external_grade',str(rows))
    def test_buggy_ignored_as_incumbent_not_erased_from_recent(self):
        rows=expected_references([n(1,.5),n(2,None,bug=True)],'1',3)
        self.assertEqual(rows[0]['roles'],['parent','incumbent','recent'])
        self.assertTrue(rows[1]['agent_marked_buggy'])
    def test_absent_parent_rejected(self):
        with self.assertRaises(ValueError):expected_references([n(1,.5)],'2',2)
    def test_synthetic_root_not_recent(self):
        root=dict(id='0',step=0,code='',exec_time=0.,parents=[])
        self.assertEqual(len(expected_references([root,n(1,.5)],'1',2)),1)


if __name__=='__main__':unittest.main()
