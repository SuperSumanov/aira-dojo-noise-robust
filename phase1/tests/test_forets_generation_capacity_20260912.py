import copy
import json
import sys
from pathlib import Path
import unittest
import sqlite3
import tempfile
from unittest.mock import patch
from contextlib import closing

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
    def test_real_mount_path_in_request(self):
        request=target.payload(target.TASKS[0],'public',16,target.MODELS[0])
        self.assertIn('/workspace/data',request['messages'][0]['content'])
        self.assertNotIn('/input',request['messages'][0]['content'])
    def test_common_json_capability_not_plus_only_schema(self):
        endpoint=dict(tag='alibaba',model_id=target.MODELS[0],context_length=1000000,max_completion_tokens=65536,
            supported_parameters=['response_format','temperature','top_p','max_tokens'],pricing=dict(prompt='0.000000195',completion='0.000000975'))
        response=dict(data=dict(endpoints=[endpoint]))
        self.assertEqual(target.catalog(response,target.MODELS[0])['response_format'],'json_object')
        endpoint['pricing']['completion']='0.1'
        with self.assertRaises(ValueError):target.catalog(response,target.MODELS[0])
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
    def test_transfer_preserves_stopped_failed_copy_and_unknown_liability(self):
        saved={k:getattr(target.budget,k) for k in ('AUTH','AUTH_RAW','AUTH_SHA','RESERVE')}
        try:
            with tempfile.TemporaryDirectory() as temp:
                parent,failed,root=[Path(temp)/x for x in ('parent','failed','new')]
                for d in (parent,failed,root):d.mkdir()
                target.budget.initialize(parent/'paid.sqlite',[f'gen-cap-{i}' for i in range(8)])
                target.budget.reserve(parent/'paid.sqlite','gen-cap-0','gen-cap-0')
                with closing(sqlite3.connect(parent/'paid.sqlite')) as db:
                    db.execute('UPDATE auth SET stopped=1');db.commit()
                    with closing(sqlite3.connect(failed/'paid.sqlite')) as out:db.backup(out)
                (failed/'generation-intent.json').write_text('{}')
                with patch.object(target,'PARENT',parent),patch.object(target,'FAILED_TRANSFER',failed),patch.object(target,'PARENT_AUTH',saved['AUTH_SHA']):
                    target.transfer(root)
                report=target.budget.snapshot(root/'paid.sqlite')
                self.assertEqual(report['unresolved'],1);self.assertEqual(report['accounted_usd'],.7)
                with closing(sqlite3.connect(root/'paid.sqlite')) as db:
                    names={r[0] for r in db.execute('SELECT scope FROM scopes')}
                    self.assertIn('gen-cap-0',names);self.assertIn(target.scope(root,0),names)
                for path in (parent,failed):
                    with closing(sqlite3.connect(path/'paid.sqlite')) as db:self.assertEqual(db.execute('SELECT stopped FROM auth').fetchone()[0],1)
                another=Path(temp)/'another';another.mkdir()
                with patch.object(target,'PARENT',parent),patch.object(target,'FAILED_TRANSFER',failed),patch.object(target,'PARENT_AUTH',saved['AUTH_SHA']):
                    with self.assertRaises(FileExistsError):target.transfer(another)
        finally:
            for k,v in saved.items():setattr(target.budget,k,v)

if __name__=='__main__':unittest.main()
