import unittest
from image_cpu_partition_20261011 import partition

class PartitionTests(unittest.TestCase):
    def rows(self,smt):
        return [dict(logical_cpu=i+32*j,socket=0,core=i) for j in range(smt) for i in range(12,16)]
    def test_observed_eight_threads_four_cores(self):
        self.assertEqual(partition(self.rows(2)),([12,13],[14,15]))
    def test_four_threads_four_cores(self):
        self.assertEqual(partition(self.rows(1)),([12,13],[14,15]))
    def test_input_order_does_not_change_partition(self):
        self.assertEqual(partition(list(reversed(self.rows(2)))),partition(self.rows(2)))
    def test_socket_is_part_of_core_identity(self):
        rows=[dict(logical_cpu=2*s+c,socket=s,core=c) for s in (0,1) for c in (0,1)]
        self.assertEqual(partition(rows),([0,1],[2,3]))
    def test_reject_bad_entitlement(self):
        for rows in ([],self.rows(1)[:-1],self.rows(1)+[dict(logical_cpu=16,socket=0,core=16)],self.rows(2)+self.rows(2)[:1]):
            with self.assertRaises(ValueError):partition(rows)

if __name__=='__main__':unittest.main()
