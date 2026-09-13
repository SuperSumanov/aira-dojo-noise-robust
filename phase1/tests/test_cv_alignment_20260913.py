from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from readout_cv_alignment_20260913 import measure
from forets_cv_alignment_contract_20260913 import instrument


class AlignmentTests(unittest.TestCase):
    def test_permutation_can_destroy_perfect_predictions(self):
        d=measure([0,0,1,1],[1,1,0,0],[0,0,1,1],[2,3,0,1],[1]*4)
        self.assertEqual(d['original_concatenated_accuracy'],0.)
        self.assertEqual(d['aligned_accuracy'],1.)
    def test_identity_no_gain(self):
        d=measure([0,1],[0,0],[0,0],[0,1],[1,1])
        self.assertEqual(d['aligned_minus_original'],0.)
    def test_does_not_guarantee_positive(self):
        d=measure([0,1],[0,1],[1,0],[1,0],[1,1])
        self.assertEqual(d['aligned_minus_original'],-1.)
    def test_different_models_rejected(self):
        with self.assertRaises(ValueError):measure([0,1],[0,1],[0,0],[0,1],[1,1])
    def test_duplicate_or_missing_rows_rejected(self):
        with self.assertRaises(ValueError):measure([0,1],[0,1],[0,1],[0,0],[1,1])
        with self.assertRaises(ValueError):measure([0,1],[0,1],[0,1],[0,1],[1,0])
    def test_instrument_exact_anchors_and_final_predictions_untouched(self):
        code='import numpy as np\nstudy = optuna.create_study(direction="maximize")\npredictions = []\nfor a in b:\n    predictions.extend(pred_labels)\ncv_score = accuracy_score(y, predictions)\nfinal_predictions = []\n'
        out,_=instrument(code)
        self.assertEqual(out.count('final_predictions = []'),1)
        self.assertIn('diag_oof[val_idx] = pred_labels',out)
        with self.assertRaises(ValueError):instrument(out)


if __name__=='__main__':unittest.main()
