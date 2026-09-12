import ast
import asyncio
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PHASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('variant',PHASE/'forets_rank_budget_variant_20260912.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)

class VariantTests(unittest.TestCase):
    def test_two_vote_reference_retained_and_source_unchanged(self):
        raw=(PHASE/'forets_contextual_rank_20260912.py').read_text();before=str(raw)
        new=v.variant(raw,2);ast.parse(new)
        self.assertIn('result=borda(rankings,n)',new)
        self.assertIn('aggregation=\'two_order_borda_v1\'',new)
        self.assertEqual(raw,before)
    def test_single_vote_source_is_bounded_and_explicit(self):
        new=v.variant((PHASE/'forets_contextual_rank_20260912.py').read_text(),1);ast.parse(new)
        self.assertIn('][:1];rankings=[]',new)
        self.assertIn('single_order_rank_v1',new)
        self.assertIn('else None)',new)
    def test_single_scores_preserve_every_permutation(self):
        for n in (3,4):
            for ranking in itertools.permutations(range(n)):
                scores=[float(n-ranking.index(i)) for i in range(n)]
                self.assertEqual(sorted(range(n),key=lambda i:-scores[i]),list(ranking))
    def test_no_approximate_patch_or_unfrozen_vote_counts(self):
        raw=(PHASE/'forets_contextual_rank_20260912.py').read_text()
        for bad in (0,3,True,1.5):
            with self.assertRaises(ValueError):v.variant(raw,bad)
        with self.assertRaises(ValueError):v.variant(raw.replace('orders=[','changed_orders=['),1)

    def test_actual_rank_function_request_count_timing_and_reverse_remap_without_network(self):
        raw=(PHASE/'forets_contextual_rank_20260912.py').read_text()
        for votes in (1,2):
            with self.subTest(votes=votes),tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);description=base/'data/leaf-classification/prepared/public/description.md'
                description.parent.mkdir(parents=True);description.write_text('fixture task')
                requests=[];reserved=[];settled=[]
                class Client:
                    def __init__(self,**kw):pass
                    async def __aenter__(self):return self
                    async def __aexit__(self,*args):pass
                    async def post(self,url,json,headers):
                        self_outer=json_module
                        self_payload=json
                        requests.append(self_payload)
                        shown=self_outer.loads(self_payload['messages'][1]['content'])['candidates']
                        ranked=sorted(range(4),key=lambda i:shown[i]['code'])
                        data={'model':'qwen/qwen3-coder-plus','provider':'alibaba','usage':{},
                              'choices':[{'finish_reason':'stop','message':{'content':self_outer.dumps({'ranking':ranked})}}]}
                        return types.SimpleNamespace(raise_for_status=lambda:None,json=lambda:data,content=self_outer.dumps(data).encode())
                json_module=json
                paid=types.SimpleNamespace(reserve=lambda *a,**kw:reserved.append((a,kw)),settle=lambda *a:(settled.append(a) or .001))
                mods={'httpx':types.SimpleNamespace(AsyncClient=Client),
                    'dojo.core.solvers.llm_helpers.backends':types.SimpleNamespace(paid_budget=paid),
                    'dojo.solvers.fore_ts.context_environment':types.SimpleNamespace(CONTEXT='fixture env')}
                ns={};exec(compile(v.variant(raw,votes),'rank_variant','exec'),ns)
                ns['Path']=lambda x:base/'data' if str(x)=='/research/d7/spc/yzyang4/mle-bench-data' else Path(x)
                with patch.dict(sys.modules,mods),patch.dict(os.environ,{'PRIMARY_KEY':'fixture-not-a-credential','FORETS_PAID_LEDGER':str(base/'no-real-ledger'),'FORETS_PAID_SCOPE':'fixture'}):
                    scores=asyncio.run(ns['rank_pool']('leaf-classification',['a','b','c','d'],1,base/'checkpoint'))
                self.assertEqual(scores,[4.,3.,2.,1.])
                self.assertEqual((len(requests),len(reserved),len(settled)),(votes,votes,votes))
                finished=json.loads((base/'checkpoint/forets-contextual-judge-private/batch-1/finished.json').read_text())
                self.assertEqual(len(finished['rank_timings']),votes)
                self.assertEqual(finished['top2_order_invariant'],True if votes==2 else None)
                self.assertTrue(all(x['request_through_parse_seconds']>=0 for x in finished['rank_timings']))

if __name__=='__main__':unittest.main()
