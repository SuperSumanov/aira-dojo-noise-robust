from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_observed_repair_memory_20260913 import eligible_transitions


def pair():
    return [dict(step=1, exec_time=1, exit_code=1, code='x = 1\n', term_out='ValueError: issue',
        is_buggy=True, parents=[], operators_used=['draft']),
        dict(step=2, exec_time=1, exit_code=0, code='x = 2\n', term_out='',
        is_buggy=False, metric=0.0, metric_info={'valid_submission': 1}, parents=[1], operators_used=['debug'])]


class RepairInventoryTests(unittest.TestCase):
    def test_zero_metric_not_filtered_and_no_score_exported(self):
        selected, exclusions=eligible_transitions(pair())
        self.assertEqual(len(selected),1); self.assertEqual(exclusions,{})
        self.assertNotIn('metric', selected[0]); self.assertEqual(selected[0]['added_lines'],1)

    def test_low_high_metric_same_selection(self):
        a=pair(); b=pair(); b[1]['metric']=0.99
        self.assertEqual(eligible_transitions(a),eligible_transitions(b))

    def test_unknown_exit_never_success(self):
        nodes=pair(); nodes[1]['exit_code']=None
        self.assertEqual(eligible_transitions(nodes)[0],[])

    def test_schema_valid_does_not_override_bug(self):
        nodes=pair(); nodes[1]['is_buggy']=True
        self.assertEqual(eligible_transitions(nodes)[0],[])

    def test_missing_measurement_parent_is_not_execution_failure(self):
        nodes=pair(); nodes[0]['exit_code']=0
        self.assertEqual(eligible_transitions(nodes)[0],[])

    def test_parallel_or_unchanged_code_not_a_repair(self):
        nodes=pair(); nodes[1]['operators_used']=['draft']
        self.assertEqual(eligible_transitions(nodes)[0],[])
        nodes=pair(); nodes[1]['code']=nodes[0]['code']
        self.assertEqual(eligible_transitions(nodes)[0],[])


if __name__ == '__main__': unittest.main()
