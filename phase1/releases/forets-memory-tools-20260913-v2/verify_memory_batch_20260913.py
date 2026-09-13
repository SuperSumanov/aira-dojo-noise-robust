"""Production batch and actual contextual request with fake transport, no API/GPU."""
from contextlib import closing
import copy
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_environment_build_20260912 import read, write, encode, sha


def run(root):
    artifact=read(root/'artifact.json')
    for name,digest in artifact['source_files'].items():
        if sha((root/'source'/name).read_bytes())!=digest:raise ValueError('source drift')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')];logging.disable(logging.CRITICAL)
    from dojo.solvers.fore_ts.batch_runtime import expand_batch
    from dojo.solvers.fore_ts import contextual_rank as rank
    from dojo.core.solvers.utils.response import extract_code
    from dojo.solvers.mcts.mcts import MCTSNode
    from dojo.core.solvers.utils.metric import MetricValue
    from dojo.core.solvers.utils.journal import Journal
    from dojo.core.tasks.constants import EXECUTION_OUTPUT
    from dojo.core.interpreters.base import ExecutionResult
    from dojo.core.solvers.llm_helpers.backends import paid_budget
    from verify_branching_selection_20260913 import verify_pool
    records=[]
    with tempfile.TemporaryDirectory(prefix='reference-cpu-',dir=root) as temp:
        temp=Path(temp)
        for arm in ('no_memory','execution_memory'):
            planned=next(r for r in read(root/'prepared.json')['run_configs'] if r['arm']==arm)
            cfg=copy.deepcopy(read(root/'configs'/(planned['run_id']+'.json'))['solver'])
            cfg['checkpoint_path']=str(temp/arm)
            tree_root=MCTSNode(code='',parents=[]);journal=Journal();journal.append(tree_root)
            solver=NS(cfg=NS(**cfg),state=NS(current_step=1,running_time=0.),task_name='leaf-classification',
                task_desc='synthetic fixture',data_preview='synthetic fixture',journal=journal,
                journal_for_unselected=Journal(),global_min_q_val=0.,global_max_q_val=1.,critic_top_k=2,
                num_children_to_choose=2,remaining_steps=63)
            count=dict(generation=0,ranking=0,execution=0,reservation=0,settlement=0)
            async def generate(*args):
                count['generation']+=1
                return MCTSNode(code=extract_code('print('+str(count['generation'])+')'),parents=[],operators_metrics=[])
            def parse(node,eval_result):
                node.absorb_exec_result(eval_result[EXECUTION_OUTPUT]);node.is_buggy=False
                node.metric=MetricValue(.5,maximize=False,info={'hidden_test_marker':'MUST_NOT_BE_IN_REQUEST'})
            def step(state,code):
                count['execution']+=1;result=ExecutionResult.get_empty()
                result.exit_code=0;result.timed_out=False;result.exec_time=.01
                return state,{EXECUTION_OUTPUT:result}
            async def reserve(*args,**kwargs):count['reservation']+=1
            def settle(*args,**kwargs):count['settlement']+=1;return 0.
            class Client:
                def __init__(self,*a,**k):pass
                async def __aenter__(self):return self
                async def __aexit__(self,*a):pass
                async def post(self,url,*,json,headers):
                    import json as js
                    count['ranking']+=1
                    payload=js.loads(json['messages'][1]['content']);ref=payload['executed_reference_context']
                    assert count['execution']==1  # Not one displayed candidate executed yet.
                    assert ref['decision_step']==2 and len(ref['references'])==1
                    assert set(ref['references'][0]['roles'])=={'parent','incumbent','recent'}
                    assert ref['references'][0]['search_validation']==.5
                    assert 'MUST_NOT_BE_IN_REQUEST' not in js.dumps(json)
                    raw={'model':rank.MODEL,'provider':'alibaba','usage':{},'choices':[
                        {'finish_reason':'stop','message':{'content':js.dumps({'ranking':[3,2,1,0]})}}]}
                    return NS(raise_for_status=lambda:None,json=lambda:raw,content=js.dumps(raw).encode())
            solver._draft=solver._improve=generate;solver.parse_eval_result=parse
            solver.log_journal=lambda:None;solver._backprop_step=lambda *a,**k:None;solver.set_global_q_values=lambda v:None
            import time
            now=time.monotonic_ns()
            env=dict(FORETS_PAID_LEDGER='synthetic',FORETS_PAID_SCOPE='synthetic',PRIMARY_KEY='synthetic-test-only')
            with patch('dojo.solvers.fore_ts.wallclock.budget',return_value=(now-10**9,now+600*10**9,temp)), \
                 patch('httpx.AsyncClient',Client),patch.object(paid_budget,'reserve_async',reserve), \
                 patch.object(paid_budget,'settle',settle),patch.dict(os.environ,env):
                state={'solver_interpreter':NS(timeout=300)}
                expand_batch(solver,[tree_root],state,NS(step_task=step),MCTSNode,extract_code,cfg)
                baseline=journal.nodes[-1]
                expand_batch(solver,[tree_root,baseline],state,NS(step_task=step),MCTSNode,extract_code,cfg)
            assert count==dict(generation=cfg['num_children'],ranking=int(arm=='critic_topk_random'),execution=3,
                reservation=int(arm=='critic_topk_random'),settlement=int(arm=='critic_topk_random'))
            assert len(baseline.children)==2
            ck=Path(cfg['checkpoint_path']);dbpath=ck/'forets-candidates-private/batch-2.sqlite'
            with closing(sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True)) as db:
                value=json.loads(db.execute('select payload from snapshot').fetchone()[0])
            rp=ck/'forets-contextual-judge-private/batch-2'
            inp=read(rp/'input.json') if rp.exists() else None
            done=read(rp/'finished.json') if rp.exists() else None
            replay=verify_pool(value,cfg,dict(task=solver.task_name,arm='uniform_random',seed=cfg['selector_seed']),inp,done)
            records.append(dict(arm=arm,counts=count,replay=replay,actual_siblings=2))
    result=dict(status='CPU_ACTUAL_MEMORY_COMMON_BATCH_NOT_EFFICACY',source_tree=artifact['source_tree'],
        rows=records,paid_api_calls=0,gpu_dispatches=0,hidden_feedback_exported=False,
        inspector_sha256=sha(Path(__file__).read_bytes()))
    print(json.dumps(dict(result=result,sha256=write(root/'memory-batch-integration.json',encode(result)))))


if __name__=='__main__':run(Path(sys.argv[1]).resolve(strict=True))
