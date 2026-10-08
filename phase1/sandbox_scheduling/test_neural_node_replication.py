import ast
from pathlib import Path
import unittest

from neural_node_replication import worker_ast
from neural_pool_trial import schedule


class ReplicationTests(unittest.TestCase):
    def test_worker_AST_only(self):
        a='CAP=5400\ndef worker(x):\n return x\ndef run_one(x):\n return worker(x)\n'
        b=a.replace('CAP=5400','CAP=2700')
        self.assertEqual(worker_ast(a),worker_ast(b))
        self.assertNotEqual(worker_ast(a),worker_ast(a.replace('return x','return x+1')))

    def test_matrix_unchanged(self):
        rows=schedule()
        self.assertEqual(len(rows),12)
        self.assertEqual({(r['program'],r['arm'],r['repeat']) for r in rows},
                         {(p,a,k) for p in (0,1) for a in ('serial','share2') for k in range(3)})

    def test_real_worker_functions_found(self):
        code=Path(__file__).with_name('neural_pool_trial.py').read_text()
        self.assertEqual(set(worker_ast(code)),{'worker','run_one'})
        ast.parse(Path(__file__).with_name('neural_node_replication.py').read_text())


if __name__=='__main__':unittest.main()
