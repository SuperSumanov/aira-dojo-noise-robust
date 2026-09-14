import unittest
from analyze_cheap_scope_transfer_20260914 import expected_validity,identity
class Tests(unittest.TestCase):
    def test_strict_and_tied_choice(self):
        self.assertEqual(expected_validity([.2,.8],[0,1]),1)
        self.assertEqual(expected_validity([.8,.2],[0,1]),0)
        self.assertEqual(expected_validity([.2,.2],[0,1]),.5)
        self.assertEqual(expected_validity([.2,.2],[1,1]),1)
    def test_unknown_rejected(self):
        for labels in ([0,None],[0,True],[0,2]):
            with self.assertRaises(ValueError):expected_validity([0.,1.],labels)
        with self.assertRaises(ValueError):expected_validity([float('nan'),1.],[0,1])
    def test_identity_semantics(self):
        a,b=identity('x = 1\n'),identity('x=1 # comment\n')
        self.assertNotEqual(a[0],b[0]);self.assertEqual(a[1],b[1]);self.assertNotEqual(a[2],b[2])
        self.assertNotEqual(identity('x='),identity('x=='))
if __name__=='__main__':unittest.main()
