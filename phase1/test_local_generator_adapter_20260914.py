import ast
import asyncio
import json
import logging
from pathlib import Path
import subprocess
import sys
import types
import unittest
from unittest.mock import patch as mock_patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_generator_adapter_20260914 as adapter
import forets_selfhosted_guard_20260912 as guard

TREE='b7f8ab0f65dba9877ac3af35e3e770fc32546565'
PATH='src/dojo/core/solvers/llm_helpers/backends/lite_llm.py'

class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=subprocess.check_output(['git','show',TREE+':'+PATH],text=True)
        cls.changed=adapter.patch(cls.original)
        cls.tree=ast.parse(cls.changed)
        cls.klass=next(n for n in cls.tree.body if isinstance(n,ast.ClassDef) and n.name=='LiteLLMClient')

    def method(self, name, **scope):
        node=next(n for n in self.klass.body if getattr(n,'name',None)==name)
        ns={'__package__':'local_fixture',**scope}
        future=ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)
        module=ast.fix_missing_locations(ast.Module(body=[future,node],type_ignores=[]))
        exec(compile(module,PATH,'exec'),ns)
        return ns[name]

    def test_exact_patch_and_unrelated_methods_unchanged(self):
        with self.assertRaises(ValueError):adapter.patch(self.changed)
        original=next(n for n in ast.parse(self.original).body if isinstance(n,ast.ClassDef) and n.name=='LiteLLMClient')
        modified={'__init__','_query_client','_query_once_bounded'}
        for old,new in zip(original.body,self.klass.body):
            if getattr(old,'name',None) not in modified:self.assertEqual(ast.dump(old),ast.dump(new))

    def test_native_constructor_no_global_auth_fallback(self):
        env={'PRIMARY_KEY':'synthetic-global-fixture'}
        os=types.SimpleNamespace(environ=env,getenv=lambda key,default='':env.get(key,default))
        init=self.method('__init__',os=os,logging=logging)
        cfg=types.SimpleNamespace(model_id=guard.MODEL,base_url='http://127.0.0.1:8000/v1',provider='selfhosted',use_azure_client=False)
        module=types.ModuleType('local_fixture.selfhosted_guard');module.selfhosted_key=guard.selfhosted_key
        with mock_patch.dict(sys.modules,{'local_fixture.selfhosted_guard':module}):
            with self.assertRaises(ValueError):init(types.SimpleNamespace(),cfg)
            env[guard.VARIABLE]='synthetic-local-fixture'
            client=types.SimpleNamespace();init(client,cfg)
            self.assertEqual(client.api_key,env[guard.VARIABLE])

    def test_native_query_rejects_unbounded_or_retried_local_calls(self):
        query=self.method('_query_client')
        client=types.SimpleNamespace(provider='selfhosted')
        for kwargs in ({},{'bounded_transport':False},{'bounded_transport':True,'bounded_max_attempts':2}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                asyncio.run(query(client,[],kwargs))

    def run_once(self, *, local=True, seconds=1200, paid=False, altered_auth=False):
        import math,time
        key='synthetic-local-fixture'
        env={guard.VARIABLE:key}
        calls=[]
        async def completion_fn(**kwargs):
            calls.append(kwargs)
            choice=types.SimpleNamespace(message=types.SimpleNamespace(content='fixture'),finish_reason='length')
            return types.SimpleNamespace(choices=[choice],to_dict=lambda:{'usage':{'prompt_tokens':5,'completion_tokens':8}})
        fn=self.method('_query_once_bounded',math=math,time=time,json=json,asyncio=asyncio,
             httpx=types.SimpleNamespace(Timeout=lambda seconds:seconds),
             os=types.SimpleNamespace(environ=env,getenv=lambda k:None),logger=logging.getLogger('fixture'),completion_fn=completion_fn)
        client=types.SimpleNamespace(provider='selfhosted' if local else 'alibaba',model='openai/qwen3.8-27b' if local else 'openai/qwen3-coder-flash',
             base_url='http://127.0.0.1:8000/v1',api_key='changed-fixture' if altered_auth else key)
        module=types.ModuleType('local_fixture.selfhosted_guard');module.selfhosted_key=guard.selfhosted_key
        with mock_patch.dict(sys.modules,{'local_fixture.selfhosted_guard':module}):
            output=asyncio.run(fn(client,[{'role':'user','content':'fixture'}],{'max_tokens':32768,'bounded_paid_budget_required':paid},None,'json',seconds))
        return output,calls

    def test_long_local_deadline_preserves_truncation_and_resource_accounting(self):
        (text,stats),calls=self.run_once()
        self.assertEqual(text,'fixture');self.assertEqual(len(calls),1)
        self.assertEqual(stats['finish_reason'],'length')
        self.assertTrue(stats['gpu_cost_accounted_separately'])
        self.assertEqual(stats['cost_status'],'local_api_no_charge_excludes_gpu')
        self.assertEqual(calls[0]['max_retries'],0);self.assertEqual(calls[0]['num_retries'],0)

    def test_old_provider_deadline_not_widened(self):
        with self.assertRaises(ValueError):self.run_once(local=False,seconds=1200)
        _,calls=self.run_once(local=False,seconds=300)
        self.assertEqual(len(calls),1)

    def test_invalid_timeout_and_paid_route_and_auth_drift_fail_before_call(self):
        for kwargs in ({'seconds':1201},{'seconds':float('inf')},{'seconds':True},{'paid':True},{'altered_auth':True}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.run_once(**kwargs)

if __name__=='__main__':unittest.main()
