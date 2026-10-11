import collections,inspect,unittest
import joint_four_capacity_20261011 as c
class Tests(unittest.TestCase):
    def test_a_fixed_matrix(self):
        rows=c.schedule();self.assertEqual(len(rows),10)
        self.assertEqual([sum(r['block']==b for r in rows) for b in range(4)],[1,1,4,4])
        self.assertEqual(collections.Counter(r['program'] for r in rows),{0:5,1:5})
    def test_b_controller_only_denominator_changed(self):
        old=inspect.getsource(c.r.controller);new=c.controller_source(old)
        self.assertNotIn('planned=14',new);self.assertIn('planned=10',new)
        self.assertIn('complete!=10',new);self.assertIn('for x in requests)!=10',new)
        self.assertEqual(old.count('140'),new.count('140'))
        compile(new,'test-controller','exec')
    def test_c_activation_roots(self):
        c.activate();self.assertEqual(len(c.r.schedule()),10);self.assertEqual(c.r.CAP,2400)
        for mod in (c.g,c.g.g,c.g.g.s,c.g.g.m,c.e,c.r,c.s,c.d):self.assertEqual(mod.ROOT,c.ROOT)
if __name__=='__main__':unittest.main()
