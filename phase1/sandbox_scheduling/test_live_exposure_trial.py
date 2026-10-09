import ast
from pathlib import Path
import unittest
import live_exposure_trial as e


class ExposureTests(unittest.TestCase):
    def test_matrix(self):
        rows=e.schedule();self.assertEqual(len(rows),4)
        self.assertEqual([r['seed'] for r in rows],list(range(174901,174905)))
        self.assertEqual([r['task'] for r in rows],list(e.t.TASKS)*2)
        self.assertEqual({r['arm'] for r in rows},{'share2'})
    def test_budget(self):
        self.assertEqual(e.SECONDS,3000);self.assertEqual(e.t.CAP,3900)
        self.assertEqual(e.t.CAP*3/3600,3.25)
        self.assertIn(3090,e.t.run_one.__code__.co_consts)
        self.assertIn(3000,e.t.cpu.__code__.co_consts)
        self.assertNotIn(600,e.t.cpu.__code__.co_consts)
    def test_shim_interface(self):
        self.assertTrue(callable(e.host));self.assertEqual(e.t.host,e.host)
        self.assertEqual(e.t.NAME,'live_exposure_trial.py')
    def test_policy_not_modified(self):
        tree=ast.parse(Path(e.__file__).read_text(encoding='utf-8'))
        for n in ast.walk(tree):
            if isinstance(n,ast.Assign):
                for target in n.targets:
                    self.assertNotIn("['num_children']",ast.unparse(target))
        self.assertEqual(e.t.ADMISSION_LIMITS,{'share2':2})


if __name__=='__main__':unittest.main()
