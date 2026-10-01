import importlib.util
import itertools
from pathlib import Path
import unittest

SPEC=importlib.util.spec_from_file_location('span',Path(__file__).parents[1]/'scripts/task_span_reference_20261002.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)

class Tests(unittest.TestCase):
    def test_alignment(self):
        self.assertEqual(M.target(dict(text='I love this!',selected_text='love this!')), [0,1,1])
    def test_unmatched(self):
        self.assertIsNone(M.target(dict(text='a b',selected_text='missing')))
    def test_unicode_offset_expansion_excluded(self):
        self.assertIsNone(M.target(dict(text='\u0130 love this',selected_text='love')))
    def test_partial_token_is_overlap(self):
        self.assertEqual(M.target(dict(text='hello!',selected_text='hello')), [1])
    def test_tie_first(self):
        self.assertEqual(M.decode('a b c',[-1,-1,-1],0),'a')
    def test_empty(self):
        self.assertEqual(M.decode('',[],0),'')
    def test_features_no_label(self):
        a=dict(text='a b',sentiment='positive',selected_text='a')
        b=dict(a,selected_text='b')
        self.assertEqual(M.features(a),M.features(b))
    def test_span_matches_exhaustive(self):
        for values in itertools.product((-1,0,2),repeat=4):
            selected=M.decode('a b c d',values,0).split()
            start=['a','b','c','d'].index(selected[0]); end=start+len(selected)
            self.assertEqual(sum(values[start:end]),max(sum(values[i:j]) for i in range(4) for j in range(i+1,5)))

if __name__=='__main__': unittest.main()
