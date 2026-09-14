import unittest
from cheap_size_only_ablation_20260914 import size_features
from verify_task_validity_20260914 import vector
class Tests(unittest.TestCase):
    def test_matches_first_two_full_features(self):
        for code in ('x=1\n','x=', '# unicode文字\nx=2\n', 'x=1\n'*10000):
            self.assertEqual(size_features(code),vector(code)[:2])
    def test_fixed_prefix(self):
        prefix='#'+'a'*29999
        self.assertEqual(size_features(prefix+'\nlong tail'),size_features(prefix))
if __name__=='__main__':unittest.main()
