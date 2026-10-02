import importlib.util
import itertools
from pathlib import Path
import random
import unittest

p=Path(__file__).resolve().parents[1]/'scripts/rank_locality_guard_20261002.py'
spec=importlib.util.spec_from_file_location('guard',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def auc(labels,scores):
    pairs=[(i,j) for i,y in enumerate(labels) for j,z in enumerate(labels) if y==1 and z==0]
    return sum((scores[i]>scores[j])+.5*(scores[i]==scores[j]) for i,j in pairs)/len(pairs)


class Guard(unittest.TestCase):
    def test_counterexample(self):
        p=[.4,.6,.8,.3,.35];c=[.2,.1,.8,.3,.35];g=[0,0,1,1,1];y=[1,0,1,0,0]
        out=m.project(p,c,g)
        self.assertTrue(m.certificate(p,out,g));self.assertAlmostEqual(auc(y,p),5/6)
        self.assertAlmostEqual(auc(y,c),2/3);self.assertAlmostEqual(auc(y,out),1.)
    def test_mixed_tie_locked(self):
        p=[.2,.2,.4];g=[0,1,0];out=m.project(p,[.8,.9,.1],g)
        self.assertEqual(out,p)
    def test_same_group_permits_reorder(self):
        self.assertEqual(m.project([.2,.4,.8],[.9,.5,.1],[0,0,0]),[.8,.4,.2])
    def test_all_alternating_locked(self):
        p=[.1,.2,.3,.4];self.assertEqual(m.project(p,p[::-1],[0,1,0,1]),p)
    def test_child_tie_keeps_parent_order(self):
        p=[.1,.3,.2];self.assertEqual(m.project(p,[.2]*3,[0]*3),p)
    def test_exhaustive_cross_group_and_loss_decomposition(self):
        rng=random.Random(102601)
        for _ in range(300):
            n=6;p=[rng.choice([0.,.25,.5,.75,1.]) for _ in range(n)]
            c=[rng.choice([0.,.25,.5,.75,1.]) for _ in range(n)];g=[rng.randrange(3) for _ in range(n)]
            out=m.project(p,c,g);self.assertTrue(m.certificate(p,out,g))
            for y in itertools.product((0,1),repeat=n):
                if not 0<sum(y)<n:continue
                delta=0.
                for i in range(n):
                    for j in range(n):
                        if y[i]!=1 or y[j]!=0 or g[i]!=g[j]:continue
                        delta+=(out[i]>out[j])+.5*(out[i]==out[j])-(p[i]>p[j])-.5*(p[i]==p[j])
                self.assertAlmostEqual(auc(y,out)-auc(y,p),delta/(sum(y)*(n-sum(y))))


if __name__=='__main__':unittest.main()
