import unittest
from generation_joint_service_audit_20261012 import parse,boundary,epoch


class ServiceAuditTests(unittest.TestCase):
    def test_no_raw_log_export(self):
        rows,missing=parse('INFO 10-12 06:00:00 internal private text Running: 0 reqs, Waiting: 0 reqs')
        self.assertEqual(rows,[dict(stamp='10-12 06:00:00',running=0,waiting=0)])
        self.assertEqual(missing,0)

    def test_missing_is_unknown(self):
        self.assertIsNone(boundary([],10,20)['zero_after_workers'])

    def test_before_workers_exit_not_evidence(self):
        self.assertIsNone(boundary([dict(time=9,running=0,waiting=0)],10,20)['zero_after_workers'])

    def test_outstanding_blocks_quiescence(self):
        self.assertFalse(boundary([dict(time=19,running=1,waiting=0)],10,20)['zero_after_workers'])

    def test_clear_after_workers(self):
        self.assertTrue(boundary([dict(time=19,running=0,waiting=0)],10,20)['zero_after_workers'])

    def test_clock_conversion(self):
        self.assertEqual(epoch('10-12 05:00:00',8),epoch('10-11 21:00:00',0))


if __name__=='__main__':unittest.main()
