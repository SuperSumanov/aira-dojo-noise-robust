import unittest
from cheap_rule_baselines_20260914 import rules,distribution,interval
class Tests(unittest.TestCase):
    def test_tuple_priority_and_ties(self):
        self.assertEqual(distribution([(1,-100),(0,-1)]).tolist(),[1.,0.])
        self.assertEqual(distribution([(1,-2),(1,-2)]).tolist(),[.5,.5])
    def test_rules(self):
        r=rules(['x = 1\n','x='])
        self.assertEqual(r['syntax_only'],[1,0]);self.assertEqual(r['fewer_lines'],[-2,-1])
        self.assertEqual(distribution(r['syntax_then_short']).tolist(),[1.,0.])
    def test_enumeration(self):
        self.assertEqual(interval([1.,0.],[0.,1.],[None,None]),(-1,1))
        self.assertEqual(interval([1.,0.],[.5,.5],[1,None]),(0,.5))
        self.assertEqual(interval([1.,0.],[1.,0.],[None,None]),(0,0))
if __name__=='__main__':unittest.main()
