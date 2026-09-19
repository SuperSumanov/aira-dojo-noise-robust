import unittest
from audit_comparison_pizza_prefix_format_20260919 import strip_exact

class NativeTrailerTests(unittest.TestCase):
    @staticmethod
    def fmt(x):return 'a moment' if x<1 else '2 hours'
    def test_exact_formatter(self):
        error="NameError: name 'col' is not defined"
        self.assertEqual(strip_exact(error+'Execution time: a moment (time limit is 2 hours).',.46,7200,self.fmt),error)
    def test_different_time_not_removed(self):
        error='NameError: badExecution time: 5 seconds (time limit is 2 hours).'
        self.assertEqual(strip_exact(error,.46,7200,self.fmt),error)
    def test_unknown_extra_text_retained(self):
        error='NameError: badExecution time: a moment (time limit is 2 hours). MISMATCH'
        self.assertEqual(strip_exact(error,.46,7200,self.fmt),error)
    def test_plain_core_unchanged(self):
        self.assertEqual(strip_exact('NameError: bad',.46,7200,self.fmt),'NameError: bad')

if __name__=='__main__':unittest.main()
