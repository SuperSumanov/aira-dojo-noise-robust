import unittest
from live_feedback_diversity import summarize


def receipt(t,code='a',output='b',valid=True):
    return dict(elapsed_seconds=t,valid=valid,code_sha256=code*64,aux={'submission_sha256':output*64})


class FeedbackDiversityTests(unittest.TestCase):
    def test_repeated_code_and_changed_code_same_submission_are_distinct_questions(self):
        r=summarize([receipt(200,'c'),receipt(100),receipt(150)])
        self.assertEqual((r['valid_returns'],r['exact_distinct_valid_codes'],r['exact_distinct_valid_submissions']),(3,2,1))
        self.assertEqual(r['feedback_count_area_seconds'],1350)
        self.assertEqual(r['distinct_code_count_area_seconds'],900)
        self.assertEqual(r['distinct_submission_count_area_seconds'],500)

    def test_late_and_invalid_are_not_positive_feedback(self):
        r=summarize([receipt(601),receipt(50,valid=False),receipt(600)])
        self.assertEqual((r['valid_returns'],r['timely_returns'],r['late_returns']),(1,2,1))
        self.assertEqual(r['feedback_count_area_seconds'],0)
        self.assertEqual(r['first_valid_seconds'],600)

    def test_no_valid_is_missing_first_return_not_zero(self):
        self.assertIsNone(summarize([])['first_valid_seconds'])
        self.assertIsNone(summarize([receipt(40,valid=False)])['first_valid_seconds'])

    def test_bad_receipt_fails_closed(self):
        for c in (receipt(-1),receipt(float('nan')),receipt(1,code='z'),receipt(1,valid=1)):
            with self.assertRaises(ValueError):summarize([c])


if __name__=='__main__':unittest.main()
