"""Role-conditioned inference effort, with shared greedy search in EVERY arm."""
import contextvars
import inspect
import time
import feedback_parent_policy_20261012 as parent
from deferred_alarm_transaction_20261012 import protect

ARMS=('medium','fast_code','feedback_think')
ORDER=ARMS+tuple(reversed(ARMS))

def thinking(arm,role):
    if arm not in ARMS or role not in ('draft','improve','debug','analyze'):
        raise ValueError('unknown arm/role')
    return role=='analyze' or arm=='medium' or (arm=='feedback_think' and role=='debug')

def normalize(cfg):
    import copy
    cfg=copy.deepcopy(cfg)
    for op in cfg['solver']['operators'].values():
        kw=op['llm']['generation_kwargs']
        kw.pop('reasoning_effort',None)
        kw['extra_body']['chat_template_kwargs'].pop('enable_thinking',None)
    return cfg

initialize=parent.initialize

def install(row,ep,deadline,warm):
    import live_admission
    live_admission.locked=protect(live_admission.locked)
    parent.locked=protect(parent.locked)
    parent.install(dict(row,arm='greedy'),ep,deadline,warm)
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from live_admission import append_event
    role=contextvars.ContextVar('effort_role',default=None)
    for name in ('_draft','_improve','_debug','_analyze'):
        old=getattr(MCTS,name)
        def factory(old=old,value=name[1:]):
            def call(self,*args,**kwargs):
                token=role.set(value)
                try:return old(self,*args,**kwargs)
                finally:role.reset(token)
            return call
        setattr(MCTS,name,factory())
    original=GenericLLM.__call__
    if inspect.iscoroutinefunction(original):raise ValueError('unexpected async LLM interface')
    def invoke(self,*args,**kwargs):
        r=role.get();expected=thinking(row['arm'],r)
        kw=self.generation_kwargs
        actual=kw['extra_body']['chat_template_kwargs']['enable_thinking']
        assert actual is expected and kw['reasoning_effort']==('medium' if expected else 'none')
        begin=time.monotonic();ok=False;usage={}
        try:
            output=original(self,*args,**kwargs);ok=True
            # Only numeric usage metadata, never prompt, response or thought text.
            if isinstance(output,tuple) and len(output)==2 and isinstance(output[1],dict):
                raw=output[1].get('usage',{})
                if isinstance(raw,dict):usage={k:v for k,v in raw.items() if type(v) in (int,float)}
            return output
        finally:
            append_event(ep/'effort.jsonl',dict(role=r,arm=row['arm'],enable_thinking=actual,
                 effort=kw['reasoning_effort'],success=ok,seconds=time.monotonic()-begin,usage=usage,
                 elapsed=deadline.elapsed()))
    GenericLLM.__call__=invoke
