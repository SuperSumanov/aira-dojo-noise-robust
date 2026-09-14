import unittest
from cheap_e2e_mechanism_20260914 import binary_bounds
class Bounds(unittest.TestCase):
    def test_same_unknown_choice_zero(self):self.assertEqual(binary_bounds({'a':0,'b':0},[None,None],'a','b'),[0,0])
    def test_different_both_unknown(self):self.assertEqual(binary_bounds({'a':0,'b':1},[None,None],'a','b'),[-1,1])
    def test_observed_success(self):self.assertEqual(binary_bounds({'a':0,'b':1},[1,None],'a','b'),[0,1])
    def test_observed_failure(self):self.assertEqual(binary_bounds({'a':0,'b':1},[0,None],'a','b'),[-1,0])
    def test_invalid_value(self):
        with self.assertRaises(ValueError):binary_bounds({'a':0,'b':1},[.5,None],'a','b')
if __name__=='__main__':unittest.main()
