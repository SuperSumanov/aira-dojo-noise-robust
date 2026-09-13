"""Pure helper checks; actual dojo/image execution is a separate GPU check."""
import ast
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock,patch

text=Path(__file__).with_name('forets_process_interpreter_20260914.py').read_text()
tree=ast.parse(text)
tree.body=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module=='dojo.core.interpreters.base')
           and not (isinstance(n,ast.ClassDef) and n.name=='FreshContainerInterpreter')]
d=types.ModuleType('pure_transport_helpers');exec(compile(tree,'transport-helpers','exec'),d.__dict__)


class Fresh(unittest.TestCase):
    def test_paths_and_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Path(tmp).resolve()
            self.assertEqual(d.safe_file(w,'submission.csv',relative=True),w/'submission.csv')
            for p in ('../escape',str(w.parent/'outside'),'.'):
                with self.assertRaises(ValueError):d.safe_file(w,p,relative=True)

    def test_timeout(self):
        self.assertEqual(d.positive(3),3.)
        for x in (0,-1,True,float('nan'),float('inf')):
            with self.assertRaises(ValueError):d.positive(x)

    def test_cell_command_treats_filename_as_data(self):
        name="a');raise Exception('bad.py"
        tree=ast.parse(d.cell_command(name))
        vals=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant)]
        self.assertIn(name,vals)
        self.assertEqual(sum(isinstance(n,ast.Raise) for n in ast.walk(tree)),0)
        self.assertIn('run_cell',d.cell_command('x.py'))

    def test_terminate_only_owned_group(self):
        child=Mock(pid=12345)
        with patch.object(d.os,'killpg',create=True) as kill,patch.object(d.signal,'SIGKILL',9,create=True):
            d.terminate_group(child)
            self.assertEqual([a.args[0] for a in kill.call_args_list],[12345,12345])

    def test_invalid_group_rejected(self):
        with patch.object(d.os,'killpg',create=True) as kill:
            with self.assertRaises(ValueError):d.terminate_group(Mock(pid=1))
            kill.assert_not_called()


if __name__=='__main__':unittest.main()
