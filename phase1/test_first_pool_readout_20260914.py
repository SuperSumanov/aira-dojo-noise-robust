import unittest
from readout_first_pool_replay_20260914 import compare
class Compare(unittest.TestCase):
    def test_leaf_direction(self):self.assertEqual(compare({'valid':True,'score':.25},{'valid':True,'score':.5},'leaf-classification'),(1,.25))
    def test_space_direction(self):self.assertEqual(compare({'valid':True,'score':.25},{'valid':True,'score':.5},'spaceship-titanic'),(-1,-.25))
    def test_unknown_not_failure(self):self.assertEqual(compare({'valid':None,'score':None},{'valid':False,'score':None},'leaf-classification'),(None,None))
    def test_valid_beats_invalid(self):self.assertEqual(compare({'valid':True,'score':.5},{'valid':False,'score':None},'spaceship-titanic'),(1,None))
    def test_two_invalid_tie(self):self.assertEqual(compare({'valid':False,'score':None},{'valid':False,'score':None},'leaf-classification'),(0,None))
if __name__=='__main__':unittest.main()
