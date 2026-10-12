import asyncio,contextvars,inspect,unittest
from pathlib import Path
from types import SimpleNamespace
from feedback_effort_policy_20261012 import thinking,normalize,ARMS,ORDER,traced_call
class Tests(unittest.TestCase):
    def test_exact_matrix(self):
        self.assertEqual([[thinking(a,r) for r in ('improve','debug','analyze')] for a in ARMS],
                         [[True,True,True],[False,False,True],[False,True,True]])
    def test_order_reverses(self):self.assertEqual(ORDER[3:],tuple(reversed(ORDER[:3])))
    def test_reject_unknown(self):
        with self.assertRaises(ValueError):thinking('unknown','improve')
        with self.assertRaises(ValueError):thinking('medium','unknown')
    def test_normalize_only_mode(self):
        def fixture(flag):return {'solver':{'operators':{'improve':{'llm':{'generation_kwargs':dict(seed=17,max_tokens=8192,reasoning_effort='medium' if flag else 'none',extra_body={'chat_template_kwargs':{'enable_thinking':flag}})}}}}}
        a=fixture(True);b=fixture(False)
        self.assertEqual(normalize(a),normalize(b));self.assertTrue(a['solver']['operators']['improve']['llm']['generation_kwargs']['extra_body']['chat_template_kwargs']['enable_thinking'])
        b['solver']['operators']['improve']['llm']['generation_kwargs']['seed']=19
        self.assertNotEqual(normalize(a),normalize(b))
    def test_quality_gate_needs_both_references_both_repeats(self):
        from feedback_effort_readout_20261012 import quality,TASKS
        scores={(b,t):(.999 if t==TASKS[0] else (.015 if ORDER[b]=='feedback_think' else .020)) for b in range(6) for t in TASKS}
        self.assertTrue(quality(scores)[1])
        scores[4,TASKS[1]]=.014
        self.assertFalse(quality(scores)[1])
    def test_async_and_sync_calls_are_invoked_and_sanitized(self):
        for is_async in (False,True):
            for arm in ARMS:
                for phase in ('draft','improve','debug','analyze'):
                    enabled=thinking(arm,phase);events=[];seen=[]
                    obj=SimpleNamespace(generation_kwargs=dict(reasoning_effort='medium' if enabled else 'none',extra_body={'chat_template_kwargs':{'enable_thinking':enabled}}))
                    def sync(self,number):
                        seen.append(number);return 'private text',{'usage':{'tokens':7,'private':'must not export'},'prompt':'private'}
                    async def asynchronous(self,number):
                        await asyncio.sleep(0);return sync(self,number)
                    role=contextvars.ContextVar('test_phase',default=phase)
                    wrapped=traced_call(asynchronous if is_async else sync,dict(arm=arm),Path('.'),SimpleNamespace(elapsed=lambda:1),role,lambda p,e:events.append(e))
                    self.assertEqual(inspect.iscoroutinefunction(wrapped),is_async)
                    result=asyncio.run(wrapped(obj,19)) if is_async else wrapped(obj,19)
                    self.assertEqual(result[0],'private text');self.assertEqual(seen,[19])
                    self.assertEqual(events[0]['usage'],{'tokens':7});self.assertTrue(events[0]['success'])
                    self.assertEqual(events[0]['role'],phase)
    def test_async_exception_logged_and_propagated(self):
        obj=SimpleNamespace(generation_kwargs=dict(reasoning_effort='none',extra_body={'chat_template_kwargs':{'enable_thinking':False}}));events=[]
        async def failing(self):raise RuntimeError('controlled failure')
        wrapped=traced_call(failing,dict(arm='fast_code'),Path('.'),SimpleNamespace(elapsed=lambda:1),contextvars.ContextVar('phase',default='improve'),lambda p,e:events.append(e))
        with self.assertRaises(RuntimeError):asyncio.run(wrapped(obj))
        self.assertEqual(len(events),1);self.assertFalse(events[0]['success'])
if __name__=='__main__':unittest.main()
