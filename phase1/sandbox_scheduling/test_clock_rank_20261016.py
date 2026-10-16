import unittest
from collections import Counter
import clock_rank_20261016 as m

class Protocol(unittest.TestCase):
    def test_matrix(self):
        s=m.schedule();self.assertEqual([r['index'] for r in s],list(range(16)))
        self.assertEqual(set(Counter((r['program'],r['mode']) for r in s).values()),{2})
        for r in s:self.assertEqual(r['task'],m.TASKS[r['program']//2])
    def test_same_task_pairs_and_reverse(self):
        self.assertEqual(m.groups(0),[[0],[1],[2],[3]])
        self.assertEqual(m.groups(1),[[4,5],[6,7]])
        self.assertEqual(m.groups(2),[[11,10],[9,8]])
        self.assertEqual(m.groups(3),[[15],[14],[13],[12]])
        for b in (1,2):
            for g in m.groups(b):
                self.assertEqual(m.schedule()[g[0]]['task'],m.schedule()[g[1]]['task'])
                self.assertNotEqual(g[0]%2,g[1]%2)
    def test_reused_worker_configuration(self):
        m.configure();self.assertEqual(m.base.R,m.R);self.assertEqual(m.base.schedule(),m.schedule())
        self.assertEqual(m.base.gateway_port('18812',0),m.base.gateway_port('18812',2))
        self.assertNotEqual(m.base.gateway_port('18812',2),m.base.gateway_port('18812',3))
    def test_cost(self):
        self.assertEqual(m.CAP,5400)
        self.assertLess(12*380+120,m.CAP)

if __name__=='__main__':unittest.main()
