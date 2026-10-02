import ast
import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).parents[1]/'scripts/edit_factorization_census_20261002.py'
S=importlib.util.spec_from_file_location('factor',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)

class Tests(unittest.TestCase):
    def test_equal(self):
        r,_=M.factor('a=1\n','a = 1 # comment\n');self.assertEqual(r['edit_blocks'],0)
    def test_separated_edits(self):
        r,p=M.factor('a=1\nx=0\nb=2\n','a=3\nx=0\nb=4\n')
        self.assertEqual(r['edit_blocks'],2);self.assertEqual(r['distinct_variants'],4)
        self.assertEqual([M.key(ast.parse(z)) for z in p],[M.key(ast.parse(z)) for z in ('a=3\nx=0\nb=2','a=1\nx=0\nb=4')])
    def test_insert_and_delete(self):
        r,p=M.factor('a=1\nx=0\nb=2\n','x=0\nb=2\nc=3\n')
        self.assertEqual(r['edit_blocks'],2);self.assertEqual(r['distinct_variants'],4)
    def test_whole_function_atomic(self):
        r,_=M.factor('def f():\n return 1\n','def f():\n return 2\n')
        self.assertEqual(r['edit_blocks'],1);self.assertEqual(r['distinct_variants'],2)
    def test_invalid_is_not_repaired(self):
        with self.assertRaises(SyntaxError):M.factor('a=1','def bad(')

if __name__=='__main__':unittest.main()
