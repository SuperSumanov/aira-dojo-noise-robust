import unittest
import numpy as np
from closed_output_calibration_20261017 import analyze_library


class CalibrationCheck(unittest.TestCase):
    def test_affine_only_bias(self):
        y=np.linspace(.2,.8,20)
        x=np.array([.7*y+.1])
        mask=np.arange(len(y))%2==0
        _,folds=analyze_library(x,y,(mask,~mask))
        for row in folds:
            self.assertLess(row['values']['calibrated_single'],1e-12)
            self.assertGreater(row['calibration_gain'],0)
            self.assertAlmostEqual(row['greedy_gain'],0)

    def test_greedy_gram_cancels_complementary_error(self):
        y=np.tile([.3,.6,.4,.7],5)
        error=np.tile([.04,-.03,-.02,.01],5)
        x=np.array([y+error,y-error])
        mask=np.arange(len(y))<12
        _,folds=analyze_library(x,y,(mask,~mask))
        for row in folds:
            self.assertLess(row['values']['greedy20'],1e-12)
            self.assertGreater(row['greedy_over_calibration'],0)

    def test_constant_predictions(self):
        y=np.tile([.2,.8],10);x=np.full((1,20),.1)
        mask=np.arange(len(y))<10
        _,folds=analyze_library(x,y,(mask,~mask))
        for row in folds:
            self.assertAlmostEqual(row['values']['calibrated_single'],.3)
            self.assertEqual(row['calibration_parameters'][0],0)


if __name__=='__main__':unittest.main()
