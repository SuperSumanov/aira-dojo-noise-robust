import unittest
from cheap_class_gate_20260914 import gate,distribution
class TestGate(unittest.TestCase):
    def test_default_threshold(self):self.assertEqual(gate([.5,.50000001]),[0,1])
    def test_both_classes_tie(self):
        self.assertEqual(distribution(gate([.6,.9])).tolist(),[.5,.5])
        self.assertEqual(distribution(gate([.1,.4])).tolist(),[.5,.5])
    def test_one_feasible(self):self.assertEqual(distribution(gate([.2,.8])).tolist(),[0.,1.])
if __name__=='__main__':unittest.main()
