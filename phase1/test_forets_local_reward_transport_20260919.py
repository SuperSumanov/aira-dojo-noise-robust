import ast,asyncio,io,json,types,unittest
from unittest.mock import patch
from forets_local_reward_transport_20260919 import request_score,validate_config,rank_nodes
import forets_local_reward_source_patch_20260919 as source_patch
from test_comparison_action_incumbent_20260919 import sources
from test_comparison_ready_runtime_20260919 import run

class Opener:
    def __init__(self,value=.7):self.value=value;self.calls=[]
    def open(self,request,timeout):self.calls.append((request,timeout));return io.BytesIO(json.dumps(dict(score=self.value)).encode())

def solver():return types.SimpleNamespace(cfg=types.SimpleNamespace(cheap_ranker='none',critic_max_attempts=1),critic_host='127.0.0.1',critic_port=8765,task_name='synthetic')

class LocalTransport(unittest.TestCase):
    def test_full_code_task_only_and_remaining_timeout(self):
        op=Opener();code='x=1\n'*12000;ticks=iter((1_000_000_000,2_000_000_000))
        self.assertEqual(request_score('task',code,host='127.0.0.1',port=8765,deadline_ns=4_000_000_000,clock_ns=lambda:next(ticks),opener=op),.7)
        request,timeout=op.calls[0]
        self.assertEqual(json.loads(request.data),dict(task='task',code=code));self.assertEqual(timeout,3.)
        self.assertEqual(request.full_url,'http://127.0.0.1:8765/score')
    def test_external_endpoint_never_called(self):
        op=Opener()
        with self.assertRaises(ValueError):request_score('t','x',host='example.com',port=8765,deadline_ns=10,opener=op)
        self.assertEqual(op.calls,[])
    def test_bool_nan_and_missing_budget_fail(self):
        for value in (True,float('nan'),'0.7'):
            with self.assertRaises(ValueError):request_score('t','x',host='127.0.0.1',port=8765,deadline_ns=10,clock_ns=lambda:1,opener=Opener(value))
        module=types.SimpleNamespace(budget=lambda:None)
        with patch.dict('sys.modules',{'dojo.solvers.fore_ts.wallclock':module}):
            with self.assertRaises(ValueError):asyncio.run(rank_nodes(solver(),[]))
    def test_late_and_preexpired_no_salvage(self):
        op=Opener()
        with self.assertRaises(TimeoutError):request_score('t','x',host='127.0.0.1',port=8765,deadline_ns=1,clock_ns=lambda:1,opener=op)
        self.assertEqual(op.calls,[])
        ticks=iter((0,10))
        with self.assertRaises(TimeoutError):request_score('t','x',host='127.0.0.1',port=8765,deadline_ns=10,clock_ns=lambda:next(ticks),opener=op)
    def test_retries_and_old_ranker_rejected(self):
        s=solver();s.cfg.critic_max_attempts=2
        with self.assertRaises(ValueError):validate_config(s)
        s=solver();s.cfg.cheap_ranker='legacy'
        with self.assertRaises(ValueError):validate_config(s)
    def test_actual_source_has_only_explicit_local_route(self):
        out=source_patch.build(sources());text=out[source_patch.base.RUNTIME].decode()
        self.assertNotIn('rank_pool',text);self.assertNotIn('contextual_rank',text)
        self.assertIn('scores = await rank_nodes(solver, nodes)',text)
        self.assertLess(text.index('validate_reward_config(solver)'),text.index('bootstrap = initial'))
        defaults=[n.value.value for n in ast.walk(ast.parse(out[source_patch.base.CONFIG])) if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='chosen_batch_order']
        self.assertEqual(defaults,['native'])
    def test_actual_runtime_ledger_same_scores_selection_both_orders(self):
        out={k:v.decode() for k,v in source_patch.build(sources()).items()}
        native,a=run(out,'native',local_reward=True)
        ready,b=run(out,'ready_first',local_reward=True)
        self.assertEqual(a['selected'],b['selected'])
        self.assertEqual([c['score'] for c in a['candidates']],[c['score'] for c in b['candidates']])
        self.assertEqual([t for t in native.trace if t[0] in ('generate','critic')],[t for t in ready.trace if t[0] in ('generate','critic')])
        self.assertEqual([c['intent']['role'] for c in a['task_calls']],['candidate','debug','candidate','debug'])
        self.assertEqual([c['intent']['role'] for c in b['task_calls']],['candidate','candidate','debug','debug'])

if __name__=='__main__':unittest.main()
