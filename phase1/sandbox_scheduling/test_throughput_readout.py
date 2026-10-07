import unittest
from throughput_readout import distribution,difference,overlap


class ReadoutTests(unittest.TestCase):
    def test_missing_is_not_zero(self):
        self.assertIsNone(distribution([])['median'])
        self.assertEqual(distribution([])['n'],0)

    def test_overlap_endpoints(self):
        self.assertEqual(overlap([(0,2),(2,4)])['two_or_more_seconds'],0)
        self.assertEqual(overlap([(0,3),(1,4)])['two_or_more_seconds'],2)
        self.assertEqual(overlap([(0,3),(1,4)])['max_simultaneous'],2)

    def test_output_alignment_not_row_order(self):
        a=(['Id','p'],{'a':[1.],'b':[2.]});b=(['Id','p'],{'b':[2.],'a':[1.]})
        self.assertEqual(difference(a,b)['different_values'],0)
        self.assertEqual(difference(a,(['Id','p'],{'a':[2.],'b':[2.]}))['max_abs'],1)
        with self.assertRaises(ValueError):difference(a,(['Id','p'],{'a':[1.]}))


if __name__=='__main__':unittest.main()
