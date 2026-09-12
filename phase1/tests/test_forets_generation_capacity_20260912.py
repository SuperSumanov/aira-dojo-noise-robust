import copy
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import forets_generation_capacity_20260912 as target

class GenerationTests(unittest.TestCase):
    def test_only_model_changes(self):
        for t in target.TASKS:
            a,b=[target.payload(t,'Public task specification',16,m) for m in target.MODELS]
            self.assertNotEqual(a.pop('model'),b.pop('model'));self.assertEqual(a,b)
    def test_matrix(self):
        self.assertEqual(set(target.MATRIX),{(t,s,m) for t in range(2) for s in (16,17) for m in range(2)})
        self.assertEqual(len(target.MATRIX),8)
    def test_code_unchanged_including_syntax_error(self):
        code='not valid Python !!!\n'
        value=dict(model=target.MODELS[0],provider='Alibaba',choices=[dict(finish_reason='stop',message=dict(content=json.dumps(dict(code=code))))])
        self.assertEqual(target.extract(value,target.MODELS[0]),code.encode())
        with self.assertRaises(ValueError):target.extract(value,target.MODELS[1])
        value['choices'][0]['finish_reason']='length'
        with self.assertRaises(ValueError):target.extract(value,target.MODELS[0])
    def test_no_silent_response_salvage(self):
        value=dict(model=target.MODELS[1],provider='Alibaba',choices=[dict(finish_reason='stop',message=dict(content='```python\nprint(1)\n```'))])
        with self.assertRaises(ValueError):target.extract(value,target.MODELS[1])

if __name__=='__main__':unittest.main()
