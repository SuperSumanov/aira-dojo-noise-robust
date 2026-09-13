from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_forets_reference_flat_journal_20260913 import normalize_nodes
from verify_forets_reference_records_20260913 import expected_references


def node(step,value,*,bug=False):
    return dict(id=str(step),step=step,code='code'+str(step),parents=[0],exec_time=1.,exit_code=0,
        is_buggy=bug,metric=value,metric_maximize=False,metric_info={'private':999})


class FlatTests(unittest.TestCase):
    def test_matches_nested_without_hidden_info(self):
        raw=[node(1,.5),node(2,.5),node(3,None,bug=True),node(4,.1)]
        result=expected_references(normalize_nodes(raw),'2',4)
        self.assertEqual([n['step'] for n in result],[2,1,3])
        self.assertNotIn('private',str(result))
        self.assertEqual(raw[0]['metric'],.5)
    def test_null_preserved(self):
        self.assertIsNone(normalize_nodes([node(1,None,bug=True)])[0]['metric']['value'])
    def test_bad_schemas(self):
        for value in (True,{},'0.5',float('nan'),float('inf')):
            with self.assertRaises(ValueError):normalize_nodes([node(1,value)])
    def test_direction_not_guessed(self):
        row=node(1,.5);del row['metric_maximize']
        with self.assertRaises(KeyError):normalize_nodes([row])
    def test_non_bool_direction_rejected(self):
        row=node(1,.5);row['metric_maximize']=1
        with self.assertRaises(ValueError):normalize_nodes([row])


if __name__=='__main__':unittest.main()
