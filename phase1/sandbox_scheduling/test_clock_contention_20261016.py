import ast
from collections import Counter
from pathlib import Path
import unittest
import clock_contention_20261016 as m

class Protocol(unittest.TestCase):
    def test_fixed_eight_and_abba(self):
        s=m.schedule()
        self.assertEqual([r['index'] for r in s],list(range(8)))
        self.assertEqual([s[2*b]['mode'] for b in range(4)],['solo','colocated','colocated','solo'])
        self.assertEqual(set(Counter((r['program'],r['mode']) for r in s).values()),{2})
    def test_gateway_unique_by_program(self):
        self.assertNotEqual(m.gateway_port('18807',0),m.gateway_port('18807',1))
        self.assertTrue(41000<=m.gateway_port('18807',0)<43000)
    def test_program_preserves_initialization(self):
        s=m.executable('print(1)',123)
        self.assertIn('torch.manual_seed(123)',s)
        self.assertIn('_r.seed(123)',s)
        self.assertIn('_n.random.seed(123)',s)
        ast.parse(s)
    def test_no_generation_or_fallback(self):
        source=Path(m.__file__).read_text()
        tree=ast.parse(source)
        workers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker'][0]
        text=ast.get_source_segment(source,workers)
        self.assertNotIn('MCTS(',text)
        self.assertNotIn('GenericLLM(',text)
        self.assertIn('task.step_task(state,action)',text)
    def test_full_cost_cap(self):
        self.assertEqual(m.CAP,2700)
        self.assertLess(6*380+120,m.CAP)

if __name__=='__main__':unittest.main()
