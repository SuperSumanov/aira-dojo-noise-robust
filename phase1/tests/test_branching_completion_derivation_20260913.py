import hashlib
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'releases/forets-branching-completion-tools-20260913/forets_pool_completion_20260912.py'
spec=importlib.util.spec_from_file_location('derived',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Derived(unittest.TestCase):
    def test_reversed_two_selected(self):
        codes=['a','b','c','d'];attempted={m.sha(codes[i].encode()) for i in (1,3)}
        self.assertEqual(m.unattempted_slots(codes,attempted,[3,1]),[0,2])
    def test_never_repeat_prior_code(self):
        codes=['a','b','c','d'];attempted={m.sha(codes[i].encode()) for i in (0,1,3)}
        with self.assertRaises(ValueError):m.unattempted_slots(codes,attempted,[3,1])
    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):m.unattempted_slots(['a','a','c','d'],set(),[0,1])
    def test_parent_and_source(self):
        self.assertEqual(m.PARENT.name,'forets-wallclock-20260912-y_p2tlmi')
        self.assertEqual(m.TREE,'35321718fef54f1907b469ab44334a30fe66b6cd')
if __name__=='__main__':unittest.main()
