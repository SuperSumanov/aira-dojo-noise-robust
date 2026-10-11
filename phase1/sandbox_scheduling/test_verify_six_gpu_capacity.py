import csv
import tempfile
from pathlib import Path
import unittest

from verify_six_gpu_capacity import difference, overlap, output, placement


class ReadoutTests(unittest.TestCase):
    def test_order_independent_difference_and_finite_guard(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.csv'; b=Path(d)/'b.csv'
            a.write_text('id,p\na,0.1\nb,0.2\n')
            b.write_text('id,p\nb,0.200002\na,0.1\n')
            self.assertAlmostEqual(difference(a,b),.000002)
            b.write_text('id,p\na,nan\nb,0.2\n')
            with self.assertRaises(AssertionError): output(b)

    def test_identity_and_header_changes_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.csv'; b=Path(d)/'b.csv'
            a.write_text('id,p\na,0.1\n')
            b.write_text('id,p\nb,0.1\n')
            with self.assertRaises(AssertionError): difference(a,b)
            b.write_text('id,q\na,0.1\n')
            with self.assertRaises(AssertionError): difference(a,b)

    def test_host_intervals_not_kernel_time(self):
        self.assertEqual(overlap([(1,3),(2,4),(3,5)]),2)
        self.assertEqual(overlap([(1,2),(2,3)]),1)

    def test_disjoint_placement(self):
        top=lambda start,n:[dict(logical_cpu=i,socket=0,core=i) for i in range(start,start+n)]
        service=dict(uuids=['a','b'],step='0')
        workers=[dict(gpu_uuids=[str(i)],cpu_topology=top(8+i*4,4),job='7',step=str(i+1)) for i in range(6)]
        self.assertEqual(placement(service,top(0,8),workers,'7')['gpus'],8)
        workers[5]['gpu_uuids']=['0']
        with self.assertRaises(AssertionError): placement(service,top(0,8),workers,'7')


if __name__=='__main__':unittest.main()
