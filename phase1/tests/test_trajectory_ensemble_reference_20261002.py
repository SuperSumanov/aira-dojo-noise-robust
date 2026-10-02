import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1]/'scripts/trajectory_ensemble_reference_20261002.py'
if not path.is_file():
    path = Path(__file__).resolve().parent/'trajectory_ensemble_reference_20261002.py'
spec = importlib.util.spec_from_file_location('reference', path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class Finalizers(unittest.TestCase):
    def test_binary_mean(self):
        result=m.finalize(m.TASKS[1],[[.1,.9],[.3,.5]])
        self.assertAlmostEqual(result['mean'][0],.2)
        self.assertAlmostEqual(result['mean'][1],.7)
    def test_binary_rank_scale(self):
        result=m.finalize(m.TASKS[1],[[1.,2.,3.],[100.,200.,300.]])
        self.assertEqual(result['rank_mean'],[1/3,2/3,1.])
    def test_binary_ties(self):
        result=m.finalize(m.TASKS[1],[[.1,.1,.9]])
        self.assertEqual(result['rank_mean'],[.5,.5,1.])
    def test_multiclass(self):
        result=m.finalize(m.TASKS[0],[[[.2,.3,.5]],[[.4,.3,.3]]])
        self.assertAlmostEqual(sum(result['mean'][0]),1.)
        self.assertAlmostEqual(result['mean'][0][2],.4)
    def test_mbr(self):
        result=m.finalize(m.TASKS[2],[['a b'],['a b c'],['a b d e']])
        self.assertEqual(result['consensus'],['a b'])
    def test_mbr_tie(self):
        result=m.finalize(m.TASKS[2],[['a'],['b']])
        self.assertEqual(result['consensus'],['a'])
    def test_single(self):
        result=m.finalize(m.TASKS[2],[['Hello World']])
        self.assertEqual(result['consensus'],['Hello World'])


if __name__=='__main__':unittest.main()
