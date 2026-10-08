import unittest
from audit_execution_identity import resource_check


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.allocation = dict(job='7', gpu_uuid='gpu-a', affinity=[1, 2])
        self.started = dict(affinity=[1, 2])
        self.native = dict(job='7', gpu_uuids=['gpu-a'])

    def test_complete_same_identity(self):
        self.assertTrue(resource_check(self.allocation, self.started, self.native, True))

    def test_incomplete_missing_is_explicit_not_verified(self):
        self.assertFalse(resource_check(self.allocation, None, None, False))

    def test_complete_missing_rejected(self):
        with self.assertRaises(ValueError):
            resource_check(self.allocation, self.started, None, True)

    def test_mismatched_cpu_gpu_or_allocation_rejected(self):
        cases = [(dict(affinity=[1]), self.native),
                 (self.started, dict(job='7', gpu_uuids=['gpu-b'])),
                 (self.started, dict(job='8', gpu_uuids=['gpu-a']))]
        for started, native in cases:
            with self.subTest(native=native, started=started), self.assertRaises(ValueError):
                resource_check(self.allocation, started, native, True)


if __name__ == '__main__':
    unittest.main()
