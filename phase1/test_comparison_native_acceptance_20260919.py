import unittest
from verify_comparison_native_acceptance_20260919 import native_parser,decide

class NativeAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parser,digest=native_parser();cls.parser=staticmethod(parser);cls.digest=digest
    def test_valid_finite_success_accepted(self):
        self.assertTrue(decide(self.parser,is_bug=False,metric=.4,exit_code=0,valid_guard=True))
    def test_task_guard_rejects_even_with_good_self_report(self):
        self.assertFalse(decide(self.parser,is_bug=False,metric=.4,exit_code=0,valid_guard=False))
    def test_missing_metric_rejected(self):
        self.assertFalse(decide(self.parser,is_bug=False,metric=None,exit_code=0,valid_guard=True))
    def test_execution_failure_rejected(self):
        self.assertFalse(decide(self.parser,is_bug=False,metric=.4,exit_code=1,valid_guard=True))
    def test_model_can_reject_officially_valid(self):
        self.assertFalse(decide(self.parser,is_bug=True,metric=.4,exit_code=0,valid_guard=True))

if __name__=='__main__':unittest.main()
