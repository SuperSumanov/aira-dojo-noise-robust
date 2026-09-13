import math
import unittest
from legacy_validity_transfer_20260914 import features,FEATURE_NAMES,purge,run_weights,pair_auc,ast_key,sha

def row(code,run):return dict(code=code,run=run,ast_key=ast_key(code),code_sha256=sha(code.encode()))

class Tests(unittest.TestCase):
    def test_features(self):
        for code in ('x=1','def bad(','import numpy as np\nfor i in range(4):\n print(i)'):
            f=features(code);self.assertEqual(len(f),len(FEATURE_NAMES));self.assertTrue(all(math.isfinite(x) for x in f))
        self.assertEqual(features('def bad(')[2],1)
    def test_purge(self):
        kept,n=purge([row('# comment\nx=1','a'),row('x=2','b')],[row('x=1','c')])
        self.assertEqual(n,1);self.assertEqual(kept[0]['run'],'b')
    def test_run_identity(self):
        with self.assertRaises(ValueError):purge([row('x=1','a')],[row('x=2','a')])
    def test_weights(self):
        w=run_weights([{'run':'a'},{'run':'a'},{'run':'b'}]);self.assertAlmostEqual(sum(w[:2]),w[2]);self.assertAlmostEqual(sum(w),3)
    def test_auc_ties(self):
        rows=[{'label':1,'p':.5},{'label':0,'p':.5},{'label':0,'p':.1}]
        self.assertEqual(pair_auc(rows,'p'),.75);self.assertIsNone(pair_auc(rows[:1],'p'))

if __name__=='__main__':unittest.main()
