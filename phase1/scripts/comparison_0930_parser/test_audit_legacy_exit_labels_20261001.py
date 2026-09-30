import unittest
from audit_legacy_exit_labels_20261001 import facts,GENERIC


class LabelChecks(unittest.TestCase):
    def test_default_zero_is_flagged(self):
        r=facts({'exit_code':0,'exec_time':0,'term_out':[GENERIC]})
        self.assertTrue(r['default_zero_signature']);self.assertTrue(r['generic_rejection_labeled_positive'])
    def test_actual_duration_not_assumed_quality(self):
        r=facts({'exit_code':0,'exec_time':1.25,'term_out':'ok'})
        self.assertTrue(r['positive_duration']);self.assertFalse(r['generic_parser_rejection'])
        self.assertNotIn('valid_submission',r)
    def test_unknown_duration_not_silently_zero(self):
        for duration in (None,float('nan'),-1,'0',True):
            r=facts({'exit_code':0,'exec_time':duration,'term_out':'ok'})
            self.assertFalse(r['duration_known_nonnegative']);self.assertFalse(r['zero_duration'])
    def test_wrong_exit_type_stops(self):
        with self.assertRaises(AssertionError):facts({'exit_code':True})
    def test_unknown_terminal_not_empty_success(self):
        self.assertFalse(facts({'exit_code':1,'exec_time':1})['terminal_known'])


if __name__=='__main__':unittest.main()
