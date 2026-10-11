import ast
from pathlib import Path
import unittest
from unet_capacity_20261011 import schedule, transform


class NarrowCapacityTests(unittest.TestCase):
    def test_matrix_is_explicitly_one_source(self):
        rows=schedule();self.assertEqual(len(rows),14)
        self.assertEqual({x['program'] for x in rows},{1})
        self.assertEqual([sum(x['block']==b for x in rows) for b in range(4)],[1,1,6,6])

    def test_execution_methods_unchanged(self):
        source=Path(__file__).with_name('six_gpu_capacity_20261011.py').read_text().replace("'resource-six-gpu-capacity-20261011-v1'","'resource-six-gpu-capacity-20261011-v2'")
        out=transform(source)
        funcs=lambda s:{x.name:ast.dump(x) for x in ast.parse(s).body if isinstance(x,ast.FunctionDef)}
        before,after=funcs(source),funcs(out)
        for n in before:
            if n!='schedule':self.assertEqual(before[n],after[n])
        self.assertIn('CAP=2400',out)


if __name__=='__main__':unittest.main()
