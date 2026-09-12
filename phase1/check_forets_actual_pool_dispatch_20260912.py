"""Actual batch-runtime/config wiring with artificial nodes and no execution/API.

Mocks only external generation, storage and execution effects, not dispatch.
Stops at execution intent. Tests every planned task/arm/width plus old-bug controls.
"""
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS


class ExecutionReached(Exception):pass
class UnsupportedWidth(Exception):pass


class Ledger:
    last=None
    def __init__(self,path,binding,count):
        Ledger.last=self;self.binding=binding;self.data=dict(selected=None,candidates=[dict(state='pending') for _ in range(count)])
        self.actual=None;self.freeze_seen=False
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def ensure_preexecution(self):pass
    def begin_generation(self,slot):self.data['candidates'][slot]['state']='generating'
    def generated(self,slot,node):self.data['candidates'][slot].update(state='generated',node=node)
    def freeze_pool(self):
        assert all(c['state']=='generated' for c in self.data['candidates']);self.freeze_seen=True
    def begin_score(self,slot):
        assert self.freeze_seen;self.data['candidates'][slot]['state']='scoring'
    def scored(self,slot,score):self.data['candidates'][slot].update(state='scored',score=score)
    def select(self,slots):self.data['selected']=slots
    def begin_execution(self,slot):self.actual=slot;raise ExecutionReached()


class Guard:
    def __init__(self,*args):pass
    def slot(self,slot):return nullcontext()


class Journal:
    def __init__(self):self.nodes=[]
    def node_list(self):return []
    def append(self,node):self.nodes.append(node)


def check(root,expect_skip):
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root))
    sys.path.insert(0,str(root/'source/src'))
    from dojo.solvers.fore_ts import batch_runtime as runtime
    from dojo.solvers.fore_ts.selection import choose_slots
    source=Path(runtime.__file__).resolve()
    if not source.is_relative_to(root/'source'):raise ValueError('wrong batch runtime imported')
    runtime.CandidateLedger=Ledger;runtime.BatchRequestGuard=Guard;runtime.ExecutionWitness=lambda *a:NS()
    configs=[json.loads(p.read_text()) for p in sorted((root/'configs').glob('*.json'))]
    if len(configs)!=4:raise ValueError('exact four configs required')
    cases=[];negative=0
    with tempfile.TemporaryDirectory(prefix='forets-dispatch-artificial-') as temp:
        for config in configs:
            cfg0=config['solver'];task=config['task']['name'];policy=cfg0['selection_policy']
            if cfg0['skip_redundant_critic'] is not expect_skip:raise ValueError('actual small-pool switch disagrees with plan')
            for width in (1,2,3,4):
                for flag in (expect_skip,not expect_skip):
                    cfg=NS(**cfg0);cfg.checkpoint_path=str(Path(temp)/f'{task}-{policy}-{width}-{flag}');cfg.skip_redundant_critic=flag
                    cfg.num_children=4;cfg.step_limit=6;cfg.critic_top_k=2;cfg.num_children_to_choose=1
                    parent=NS(id='synthetic-parent',parents=[],children=set())
                    solver=NS(cfg=cfg,remaining_steps=width,task_name=task,task_desc='artificial description',data_preview='',
                        state=NS(current_step=6-width),journal=Journal(),journal_for_unselected=Journal(),
                        global_min_q_val=0,global_max_q_val=1,critic_top_k=2,num_children_to_choose=1)
                    created=[];calls=[]
                    async def generate(unused):
                        i=len(created);node=NS(id=f'artificial-{i}',ctime=0,code=f'print({i})',plan='',operators_used=[],
                            operators_metrics={},parents=[],children=set(),metric=None,is_buggy=None)
                        created.append(node);return node
                    async def rank(task_name,codes,step,path):
                        assert Ledger.last.freeze_seen and len(created)==width
                        calls.append(len(codes))
                        if len(codes) not in (3,4):raise UnsupportedWidth()
                        return list(range(len(codes)))
                    solver._draft=generate;runtime.rank_pool=rank
                    failure=False
                    try:runtime.expand_batch(solver,[parent],{},NS(),NS,lambda x:x,{})
                    except ExecutionReached:pass
                    except UnsupportedWidth:failure=True
                    expected_failure=policy=='critic_topk_random' and not flag and width<=2
                    if failure!=expected_failure:raise ValueError('dispatch differs from actual frozen width guard')
                    if flag!=expect_skip:
                        negative+=expected_failure;continue
                    if failure:
                        cases.append(dict(task=task,arm=policy,width=width,accepted=False,reason='old-small-pool-defect'));continue
                    should_rank=policy=='critic_topk_random' and width>2
                    if calls!=([width] if should_rank else []):raise ValueError('unplanned rank invocation')
                    if width<=2 or policy=='uniform_random':
                        expected=choose_slots(width,2,1,'uniform_random',cfg.selector_seed,task,6-width,None,coupling=cfg.selection_coupling)
                        if Ledger.last.data['selected']!=expected:raise ValueError('small-pool/full-pool selection changed')
                    bypass=policy=='critic_topk_random' and flag and width<=2
                    if bypass!=(Ledger.last.binding.get('score_bypass')=='full_pool_no_pruning'):raise ValueError('missing explicit bypass receipt')
                    if Ledger.last.actual!=Ledger.last.data['selected'][0]:raise ValueError('wrong execution intent')
                    cases.append(dict(task=task,arm=policy,width=width,accepted=True,rank_invocations=len(calls),bypass=bypass))
    result=dict(config_count=len(configs),actual_skip_redundant_critic=expect_skip,planned_cases=len(cases),
        accepted_cases=sum(c['accepted'] for c in cases),negative_controls_reproduce_old_failure=negative,
        actual_batch_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),model_api_calls=0,gpu_jobs=0,task_executions=0,
        test_scope='actual source/config dispatch with artificial generation and stop before execution',cases=cases)
    print(json.dumps(result))
    if expect_skip and result['accepted_cases']!=16:raise ValueError('new real-config wiring not ready')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--expect-skip',choices=('true','false'),required=True);a=p.parse_args()
    check(a.root.resolve(),a.expect_skip=='true')
