import ast
import unittest
from unittest.mock import patch
import lifecycle_pilot as p


class PilotTests(unittest.TestCase):
    def test_fixed_six_counterbalanced_calls(self):
        rows = p.schedule()
        self.assertEqual(len(rows), 6)
        self.assertEqual([r['index'] for r in rows], list(range(6)))
        self.assertEqual([r['arm'] for r in rows], ['keep_10s','close_now','close_now','keep_10s','keep_10s','close_now'])
        self.assertEqual({r['seed'] for r in rows}, {130601})
        for repeat in range(3):
            self.assertEqual({r['arm'] for r in rows if r['repeat']==repeat}, {'keep_10s','close_now'})

    def test_fixture_has_no_data_or_training(self):
        tree = ast.parse(p.PROGRAM)
        calls = {getattr(n.func,'attr',getattr(n.func,'id','')) for n in ast.walk(tree) if isinstance(n,ast.Call)}
        self.assertFalse(calls & {'fit','backward','read_csv','read_parquet','load','requests','urlopen'})
        self.assertIn('synchronize',calls)
        self.assertIn('write_text',calls)

    def test_applications_is_scoped_and_does_not_assume_empty(self):
        with patch.object(p.subprocess,'check_output',return_value='GPU-test, 123\n') as query:
            self.assertEqual(p.applications('GPU-test'), [123])
        self.assertEqual(query.call_args.args[0][:3], ['nvidia-smi','-i','GPU-test'])
        with patch.object(p.subprocess,'check_output',return_value='GPU-other, 123\n'), self.assertRaises(ValueError):
            p.applications('GPU-test')
        with patch.object(p.subprocess,'check_output',return_value=''):
            self.assertEqual(p.applications('GPU-test'), [])


if __name__=='__main__':
    unittest.main(verbosity=2)
