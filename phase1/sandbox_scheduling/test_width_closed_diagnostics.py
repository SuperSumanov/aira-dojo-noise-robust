import tempfile
from pathlib import Path
import unittest
from width_closed_diagnostics import numeric_table,completion_curve,curve_comparison


class DiagnosticsTests(unittest.TestCase):
    def test_crossing_keeps_early_and_late_tradeoff(self):
        result=curve_comparison([50,100,150,200],[90,100,110,120])
        self.assertEqual(result['return_rank_differences_seconds'],[40,0,-40,-80])
        self.assertTrue(result['crosses'])
        self.assertFalse(result['b_no_later_at_every_return_rank'])

    def test_dominance_requires_every_return_rank(self):
        result=curve_comparison([20,40,60,80],[10,30,50,70])
        self.assertTrue(result['b_no_later_at_every_return_rank'])
        self.assertFalse(result['crosses'])
        self.assertEqual(completion_curve([80,20,60,40])['mean_return_seconds'],50)

    def test_missing_curve_does_not_become_zero(self):
        with self.assertRaises(ValueError): completion_curve([1,2,3])
        with self.assertRaises(ValueError): curve_comparison([1,2,3,4],[])

    def test_decimal_numeric_equality_and_invalid_tables(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path=Path(temp)/'synthetic.csv'
            path.write_text('id,p\na,0.10\nb,2\n')
            first=numeric_table(path)
            path.write_text('id,p\nb,2.000\na,0.1\n')
            self.assertEqual(first,numeric_table(path))
            for content in ('id,p\na,nan\n','id,p\na,1\na,2\n','id,p\na,1,2\n'):
                path.write_text(content)
                with self.assertRaises(ValueError): numeric_table(path)


if __name__=='__main__': unittest.main()
