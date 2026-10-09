import unittest
from twochild_prelaunch_note import corrected_prose


class NoteTests(unittest.TestCase):
    def test_prose_only(self):
        plan=dict(run_seconds=1500,candidate_timeout_seconds=240,
                  common_adapter='queue in600s deadline',primary='returns in600s')
        before=dict(plan)
        result=corrected_prose(plan)
        self.assertEqual(plan,before)
        self.assertEqual(result,dict(common_adapter='queue in1500s deadline',primary='returns in1500s'))
    def test_reject_wrong_budget_or_text(self):
        for plan in (dict(run_seconds=600,candidate_timeout_seconds=240),
                     dict(run_seconds=1500,candidate_timeout_seconds=240,common_adapter='changed')):
            with self.assertRaises(ValueError):corrected_prose(plan)


if __name__=='__main__':unittest.main()
