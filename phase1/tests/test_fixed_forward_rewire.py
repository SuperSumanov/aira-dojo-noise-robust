from dataclasses import replace
import random
import unittest
from phase1.fixed_forward_rewire import plan, verify, bce_reference


class RewireTest(unittest.TestCase):
    def triangles(self):
        return ((('a','b'),('a','c'),('b','c'),('d','e'),('d','f'),('e','f')),)

    def test_two_cycles_connect_without_more_occurrences(self):
        batches = self.triangles()
        strata = {x:'same' for x in 'abcdef'}
        result = plan(batches, strata)
        counts = verify(batches, strata, result)
        self.assertEqual((result.swaps, counts['original_components'], counts['rewritten_components']), (1,2,1))
        self.assertEqual(result.losses[0][2], (4,10))

    def test_trees_cannot_be_used_for_this_conservative_rule(self):
        batches = ((('a','b'),('b','c'),('d','e'),('e','f')),)
        strata = {x:'same' for x in 'abcdef'}
        self.assertEqual(verify(batches,strata,plan(batches,strata))['changed_pairs'],0)

    def test_stratum_mismatch_or_missing_prevents_swap(self):
        for value in ('other', None):
            strata = {x:'same' for x in 'abcdef'}
            strata['d']=strata['e']=strata['f']=value
            self.assertEqual(plan(self.triangles(),strata).swaps,0)

    def test_no_cross_microbatch_swap(self):
        edges=self.triangles()[0]
        self.assertEqual(plan((edges[:3],edges[3:]),{x:'t' for x in 'abcdef'}).swaps,0)

    def test_duplicates_fail_closed(self):
        with self.assertRaises(ValueError): plan(((('a','b'),('b','a')),),{'a':'t','b':'t'})

    def test_verifier_detects_lost_occurrence(self):
        strata={x:'t' for x in 'abcdef'}
        result=plan(self.triangles(),strata)
        bad=replace(result,losses=(((0,1),)*6,))
        with self.assertRaises(ValueError): verify(self.triangles(),strata,bad)

    def test_finite_difference_ties_and_orientations(self):
        scores=[-.7,1.2,.4,-1.8]
        for indices in (((0,1),(2,3)),((0,2),(1,3))):
            for targets in ((1.,0.),(.5,1.)):
                loss,gradient=bce_reference(scores,indices,targets)
                for i in range(4):
                    hi,lo=list(scores),list(scores)
                    hi[i]+=1e-6;lo[i]-=1e-6
                    estimate=(bce_reference(hi,indices,targets)[0]-bce_reference(lo,indices,targets)[0])/2e-6
                    self.assertAlmostEqual(estimate,gradient[i],places=8)
                rev=tuple((b,a) for a,b in indices)
                rloss,rgrad=bce_reference(scores,rev,tuple(1-y for y in targets))
                self.assertAlmostEqual(loss,rloss)
                for a,b in zip(gradient,rgrad):self.assertAlmostEqual(a,b)

    def test_extreme_logits_are_finite(self):
        import math
        loss,g=bce_reference([1000.,-1000.],((0,1),),(0.,))
        self.assertTrue(math.isfinite(loss) and all(math.isfinite(x) for x in g))

    def test_many_fixed_random_graphs(self):
        for seed in range(30):
            rng=random.Random(seed)
            edges=[(f'{c}:{i}',f'{c}:{j}') for c in range(12) for i in range(4) for j in range(i+1,4)]
            rng.shuffle(edges)
            batches=tuple(tuple(edges[i:i+8]) for i in range(0,len(edges),8))
            strata={x:'t' for e in edges for x in e}
            result=plan(batches,strata)
            verify(batches,strata,result)
            self.assertEqual(plan(batches,strata),result)


if __name__=='__main__':unittest.main()
