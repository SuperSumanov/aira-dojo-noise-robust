import unittest
from closed_fold_mechanism_20261016 import parse_folds

class FoldReceipts(unittest.TestCase):
    text='Fold 1: 1878 patches, 59 batches/epoch\nFold 1: RMSE = 0.123 | Time: 1s\nTime guard: skipping fold 2\n1-Fold CV RMSE: 0.123'
    def test_matched_receipts(self):
        self.assertEqual(parse_folds(self.text,12,708)['completed_folds'],1)
    def test_missing_completion(self):
        with self.assertRaises(AssertionError):parse_folds(self.text.replace('Fold 1: RMSE =','Missing:'),12,708)
    def test_wrong_steps(self):
        with self.assertRaises(AssertionError):parse_folds(self.text,12,709)
    def test_duplicate_start(self):
        with self.assertRaises(AssertionError):parse_folds('Fold 1: 1878 patches, 59 batches/epoch\n'+self.text,12,708)
    def test_missing_guard(self):
        with self.assertRaises(AssertionError):parse_folds(self.text.replace('Time guard: skipping fold 2',''),12,708)
    def test_does_not_export_cv_values(self):
        self.assertEqual(parse_folds(self.text,12,708),parse_folds(self.text.replace('0.123','0.987'),12,708))

if __name__=='__main__':unittest.main()
