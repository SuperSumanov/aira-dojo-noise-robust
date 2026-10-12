import unittest
from feedback_parent_partial_readout_20261012 import compare_available,TASKS


class MissingTests(unittest.TestCase):
    def test_missing_is_not_warm_start_or_zero(self):
        q={b:b<4 for b in range(6)}
        scores={(b,t):(.02 if t==TASKS[1] else .99) if q[b] else None for b in range(6) for t in TASKS}
        out=compare_available(scores,q)
        self.assertEqual(out['comparable_contrasts'],4)
        self.assertFalse(out['predeclared_success_gate_met'])
        self.assertFalse(out['full_quality_comparison_available'])
        for r in out['contrasts']:
            if r['repeat']==1:
                self.assertIsNone(r['oriented_delta']);self.assertIsNone(r['reference_best'])

    def test_first_repeat_win_cannot_rescue_full_gate(self):
        q={b:b<4 for b in range(6)}
        scores={(b,t):(.02 if b in (2,3) else .04) if t==TASKS[1] else .99 for b in range(6) for t in TASKS}
        out=compare_available(scores,q)
        self.assertTrue(out['first_repeat_meets_quality_rule'])
        self.assertFalse(out['predeclared_success_gate_met'])


if __name__=='__main__':unittest.main()
