import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from derive_reference_completion_20260913 import derive


class DeriveTests(unittest.TestCase):
    def test_partial_selected_is_completed_without_retry(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out';derive(out)
            spec=importlib.util.spec_from_file_location('worker',out/'forets_pool_completion_20260912.py')
            m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
            codes=['a','b','c','d']
            self.assertEqual(m.unattempted_slots(codes,{m.sha(b'a')},[0,2]),[1,2,3])
            self.assertEqual(m.unattempted_slots(codes,{m.sha(b'a'),m.sha(b'c')},[2,0]),[1,3])
            with self.assertRaises(ValueError):m.unattempted_slots(codes,{m.sha(b'b')},[0,2])
            with self.assertRaises(ValueError):m.unattempted_slots(['a']*4,{m.sha(b'a')},[0,2])
            reader=(out/'readout_reference_completion_20260913.py').read_text()
            self.assertIn("planned=9,attempted=done['completed']",reader)
            self.assertIn("done['planned']!=9",reader)
            self.assertNotIn('planned=8',reader)
            proof=json.loads((out/'derivation.json').read_bytes())
            for name,h in proof['files'].items():self.assertEqual(m.sha((out/name).read_bytes()),h)


if __name__=='__main__':unittest.main()
