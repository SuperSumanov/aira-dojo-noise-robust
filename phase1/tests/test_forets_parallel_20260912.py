import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import types
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from forets_parallel_patch_20260912 import patch_transport, patch_readiness

BASE='6780e383d20d6051ba53cace793f0db910027315'
PREFIX='src/dojo/core/solvers/llm_helpers/backends/'


def original(name):
    return subprocess.check_output(['git','show',BASE+':'+name],text=True)


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.source=original(PREFIX+'paid_transport.py')
        self.reserved={}; self.posts=[]; self.active=0; self.peak=0
        self.entered=asyncio.Event(); self.block=False; self.reject=False
        self.budget=types.ModuleType('forets_paid_budget_20260911')
        self.budget.MODEL='qwen/qwen3-coder-flash'; self.budget.PROVIDER={'only':['alibaba']}
        self.budget.BudgetStopped=RuntimeError
        def reserve(path,scope,ident):
            if self.reject:raise RuntimeError('synthetic insufficient reservation')
            if ident in self.reserved:raise AssertionError('duplicate request')
            self.reserved[ident]='unresolved'
        def settle(path,ident,usage):
            self.assertEqual(self.reserved[ident],'unresolved')
            self.reserved[ident]='settled';return usage['cost']
        self.budget.reserve=reserve;self.budget.settle=settle
        owner=self
        class Client:
            def __init__(self,**kwargs):
                owner.assertEqual(kwargs,dict(timeout=120,follow_redirects=False))
            async def __aenter__(self):return self
            async def __aexit__(self,*args):return None
            async def post(self,url,**kwargs):
                owner.posts.append((url,kwargs['json']))
                owner.active+=1;owner.peak=max(owner.peak,owner.active);owner.entered.set()
                try:
                    if owner.block:await asyncio.Event().wait()
                    await asyncio.sleep(.005)
                    return types.SimpleNamespace(raise_for_status=lambda:None,json=lambda:dict(usage={'cost':.01}))
                finally:owner.active-=1
        self.modules={'forets_paid_budget_20260911':self.budget,
                      'httpx':types.SimpleNamespace(AsyncClient=Client),
                      'litellm':types.SimpleNamespace(ModelResponse=lambda **raw:types.SimpleNamespace(**raw))}
        self.kwargs=dict(model='openai/'+self.budget.MODEL,base_url='https://openrouter.ai/api/v1',
                         extra_body={'provider':self.budget.PROVIDER},max_tokens=8192,api_key='synthetic-not-a-key',temperature=.6)
        self.messages=[dict(role='user',content='public synthetic fixture')]

    def module(self, source):
        module=types.ModuleType('synthetic_parallel_transport');module.__package__=''
        exec(compile(source,'<actual patched transport>','exec'),module.__dict__)
        return module

    async def test_wire_payload_and_bounded_actual_concurrency(self):
        with patch.dict(sys.modules,self.modules),patch.dict(os.environ,FORETS_PAID_LEDGER='/synthetic',FORETS_PAID_SCOPE='synthetic'):
            old=self.module(self.source);new=self.module(patch_transport(self.source))
            self.assertEqual(old.payload_for(self.messages,self.kwargs),new.payload_for(self.messages,self.kwargs))
            responses=await asyncio.gather(*(new.complete(self.messages,self.kwargs,120,str(i)) for i in range(9)))
            self.assertEqual(self.peak,4);self.assertEqual(len(self.posts),9)
            self.assertEqual(list(self.reserved.values()),['settled']*9)
            self.assertTrue(all(r.usage['cost']==.01 for r in responses))

    async def test_cancel_keeps_reservation_and_no_retry(self):
        self.block=True
        with patch.dict(sys.modules,self.modules),patch.dict(os.environ,FORETS_PAID_LEDGER='/synthetic',FORETS_PAID_SCOPE='synthetic'):
            new=self.module(patch_transport(self.source))
            task=asyncio.create_task(new.complete(self.messages,self.kwargs,120,'cancel'))
            await asyncio.wait_for(self.entered.wait(),1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(self.reserved,{'cancel':'unresolved'})
            self.assertEqual(len(self.posts),1);self.assertEqual(new._ACTIVE[asyncio.get_running_loop()],0)

    async def test_no_wire_before_reservation(self):
        self.reject=True
        with patch.dict(sys.modules,self.modules),patch.dict(os.environ,FORETS_PAID_LEDGER='/synthetic',FORETS_PAID_SCOPE='synthetic'):
            new=self.module(patch_transport(self.source))
            with self.assertRaises(RuntimeError):await new.complete(self.messages,self.kwargs,120,'reject')
            self.assertFalse(self.posts);self.assertFalse(self.reserved)

    def test_repeated_patch_is_rejected(self):
        with self.assertRaises(ValueError):patch_transport(patch_transport(self.source))


class ReadinessTests(unittest.TestCase):
    def test_passive_counters_do_not_relax_handshake(self):
        source=patch_readiness(original('src/dojo/core/interpreters/jupyter/kernel_readiness.py'))
        ns={'__name__':'synthetic_readiness'};exec(compile(source,'<patched readiness>','exec'),ns)
        class Clock:
            value=0.
            def __call__(self):return self.value
        clock=Clock()
        class Client:
            def __init__(self):self.messages=[];self.sent=0
            def _send_message(self,**kwargs):
                self.sent+=1; ident='never-export-this-identity-'+str(self.sent)
                self.messages=[dict(parent_header={'msg_id':ident},msg_type='kernel_info_reply'),
                               dict(parent_header={'msg_id':ident},msg_type='status',content={'execution_state':'idle'})]
                return ident
            def _receive_message(self,timeout):clock.value+=.1;return self.messages.pop(0)
        with self.assertLogs('synthetic_readiness',level='INFO') as log:
            self.assertTrue(ns['wait_for_ready'](Client(),clock=clock))
        self.assertNotIn('never-export',str(log.output))
        event=json.loads(log.output[0].split('kernel_handshake ',1)[1])
        self.assertEqual(event['paired'],1);self.assertEqual(event['received'],2)

    def test_actual_budget_never_resets_or_overspends(self):
        from build_forets_parallel_20260912 import budget_source, PRIOR_HELD, NEW_CAP
        ns={};exec(compile(budget_source(original(PREFIX+'paid_budget.py')),'<actual budget>','exec'),ns)
        self.assertEqual(ns['AUTH']['total'],PRIOR_HELD+NEW_CAP)
        self.assertLessEqual(ns['AUTH']['total'],10*10**9)
        fake=types.ModuleType('dojo.solvers.fore_ts.wallclock');fake.admit_request=lambda:None
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'dojo.solvers.fore_ts.wallclock':fake}):
            path=Path(tmp)/'billing.sqlite'
            with closing(sqlite3.connect(path)) as db,db:
                db.executescript('CREATE TABLE auth(digest,body,stopped);CREATE TABLE scopes(scope,cap);CREATE TABLE calls(id PRIMARY KEY,scope,held,cost,state,created);')
                db.execute('INSERT INTO auth VALUES(?,?,0)',(ns['AUTH_SHA'],ns['AUTH_RAW'].decode()))
                db.execute('INSERT INTO scopes VALUES(?,?)',('fresh',4000000000))
                db.execute('INSERT INTO calls VALUES(?,?,?,?,?,?)',('prior','old',PRIOR_HELD,None,'unresolved',0))
            for i in range(5):ns['reserve'](path,'fresh',str(i))
            with self.assertRaises(ns['BudgetStopped']):ns['reserve'](path,'fresh','sixth')
            with closing(sqlite3.connect(path)) as db,db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM calls').fetchone()[0],6)
                self.assertEqual(db.execute('SELECT held FROM calls WHERE id="prior"').fetchone()[0],PRIOR_HELD)
            ns['settle'](path,'0',{'cost':.01})
            ns['reserve'](path,'fresh','after_settlement')
            with self.assertRaises(ns['BudgetStopped']):ns['settle'](path,'0',{'cost':.01})


if __name__=='__main__':unittest.main()
