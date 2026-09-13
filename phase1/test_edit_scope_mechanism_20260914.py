import unittest
import analyze_edit_scope_mechanism_20260914 as m


CODE = 'import os\ndef build_model(X):\n    return X\nprint(1)\n'


class Tests(unittest.TestCase):
    def test_only_top_level_model_is_removed(self):
        self.assertEqual(m.outer_key(CODE), m.outer_key(CODE.replace('return X', 'return None')))
        self.assertNotEqual(m.outer_key(CODE), m.outer_key(CODE.replace('print(1)', 'print(2)')))

    def test_saved_executed_counts_and_overlap(self):
        nodes = [
            dict(step=0, exec_time=99),
            dict(step=1, exec_time=None),
            dict(step=2, exec_time=3, exit_code=1, code=CODE,
                 term_out="TypeError: got an unexpected keyword argument; inconsistent numbers of samples",
                 operators_metrics=[dict(edit_scope=dict(interface_accepted=False, rejection='fixture'))]),
            dict(step=3, exec_time=2, exit_code=0, code=CODE.replace('return X','return None'),
                 metric_info=dict(valid_submission=1)),
        ]
        r=m.node_summary(nodes,m.outer_key(CODE))
        self.assertEqual(r['counts']['saved_executed'],2)
        self.assertEqual(r['counts']['valid_submission'],1)
        self.assertEqual(r['seconds']['saved_executed'],5)
        self.assertEqual(r['seconds']['pattern:fit_or_train_keyword'],3)
        self.assertEqual(r['seconds']['pattern:inconsistent_sample_counts'],3)
        self.assertEqual(r['counts']['interface_rejected'],1)
        self.assertEqual(r['static_outer']['static_outer_unchanged'],2)

    def test_missing_exit_is_not_claimed_success(self):
        r=m.node_summary([dict(step=1,exec_time=2,exit_code=None)],m.outer_key(CODE))
        self.assertEqual(r['counts']['nonzero_exit'],0)
        self.assertEqual(r['counts']['valid_submission'],0)

    def test_duration_and_syntax(self):
        for value in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):
                m.node_summary([dict(step=1,exec_time=value)],m.outer_key(CODE))
        r=m.node_summary([dict(step=1,exec_time=1,code='def broken(')],m.outer_key(CODE))
        self.assertEqual(r['static_outer']['syntax_unparseable'],1)


if __name__=='__main__':unittest.main()
