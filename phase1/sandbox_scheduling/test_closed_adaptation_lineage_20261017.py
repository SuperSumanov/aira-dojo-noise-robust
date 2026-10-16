import unittest
import closed_adaptation_lineage_20261017 as m

def node(step,code,role,parents=()):
    return dict(step=step,code=code,operators_used=[role],parents=list(parents))

class Lineage(unittest.TestCase):
    def test_warm_and_debug(self):
        nodes=[node(0,'warm','warm_start'),node(1,'proposal','improve',[0]),node(2,'repair','debug',[1])]
        self.assertEqual(m.lineage(nodes,m.codehash('proposal'),m.codehash('warm'))['category'],'improve_from_warm')
        self.assertEqual(m.lineage(nodes,m.codehash('repair'),m.codehash('warm'))['category'],'debug_from_warm')

    def test_imported_new_parent(self):
        nodes=[node(0,'warm','warm_start'),node(1,'peer','shared_parent'),node(2,'proposal','improve',[1])]
        self.assertEqual(m.lineage(nodes,m.codehash('proposal'),m.codehash('warm'))['category'],'improve_from_new')

    def test_unknown_and_ambiguous(self):
        nodes=[node(0,'warm','warm_start'),node(1,'peer','shared_parent'),node(2,'same','improve',[0]),node(3,'same','improve',[1])]
        self.assertFalse(m.lineage(nodes,m.codehash('missing'),m.codehash('warm'))['resolved'])
        self.assertFalse(m.lineage(nodes,m.codehash('same'),m.codehash('warm'))['resolved'])

    def test_invalid_graph(self):
        with self.assertRaises(ValueError):m.lineage([node(0,'a','debug',[0])],m.codehash('a'),'x')
        with self.assertRaises(ValueError):m.lineage([node(0,'a','warm_start'),node(0,'b','improve',[0])],'x','x')

    def test_subset_is_not_final_best(self):
        runs=[dict(index=i,block=0,task='denoising-dirty-documents',initial_score=.1,candidate_returns=2 if i==0 else 0,valid_returns=2 if i==0 else 0,pool_mode='shared') for i in range(4)]
        cc=[dict(index=0,block=0,task='denoising-dirty-documents',candidate=i,valid=True,first_attempt=i==0,
            score=s,category='improve_from_warm' if i==0 else 'debug_from_warm',pool_elapsed=(i+1)*100) for i,s in enumerate((.08,.03))]
        r=m.summarize(cc,runs,[dict(block=0,task='denoising-dirty-documents',best=.03)])[0]
        self.assertAlmostEqual(r['oriented_gain_after_first_attempts'],.05)
        self.assertEqual(r['winning_categories'],['debug_from_warm'])

if __name__=='__main__':unittest.main()
