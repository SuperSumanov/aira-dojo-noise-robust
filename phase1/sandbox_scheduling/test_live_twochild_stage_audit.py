import unittest
from live_twochild_stage_audit import counts


class StageCountsTests(unittest.TestCase):
    def test_debug_is_not_improve(self):
        result = counts([{'operators_used':[op]} for op in ('draft','debug','debug')],2)
        self.assertEqual(result['recorded_debugs'],2)
        self.assertFalse(result['recorded_improve_present'])
        self.assertTrue(result['root_draft_quota_unfinished'])

    def test_finished_root_and_improve_are_distinct(self):
        result = counts([{'operators_used':['draft']},{'operators_used':['draft']}],2)
        self.assertFalse(result['root_draft_quota_unfinished'])
        self.assertFalse(result['recorded_improve_present'])

    def test_improve_does_not_require_score_or_bug_status(self):
        result = counts([{'operators_used':['improve'],'is_buggy':True}],2)
        self.assertEqual(result['recorded_improves'],1)
        self.assertTrue(result['recorded_improve_present'])

    def test_unknown_phase_fails_closed(self):
        for node in ({},{'operators_used':[]},{'operators_used':['unknown']},{'operators_used':'draft'}):
            with self.assertRaises(ValueError): counts([node],2)

    def test_wrong_common_baseline_rejected(self):
        for children in (True,1,5):
            with self.assertRaises(ValueError): counts([],children)


if __name__ == '__main__':
    unittest.main()
