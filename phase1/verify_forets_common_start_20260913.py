"""Actual imported first/later expansion paths with synthetic task boundaries."""
import argparse
import copy
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_environment_build_20260912 import read,write,encode,sha


def run(root):
    import verify_forets_wallclock_20260912 as common
    common.run(root,blocks=(1,2))
    from dojo.solvers.fore_ts.batch_runtime import expand_batch
    from dojo.solvers.fore_ts.common_start import code_for,digest
    from dojo.core.solvers.utils.response import extract_code
    from dojo.solvers.mcts.mcts import MCTSNode
    from dojo.core.solvers.utils.journal import Journal
    from dojo.core.tasks.constants import EXECUTION_OUTPUT
    from dojo.core.interpreters.base import ExecutionResult
    import pandas as pd
    import numpy as np
    records=[]
    with tempfile.TemporaryDirectory(prefix='common-start-test-',dir=root) as temp:
        temp=Path(temp)
        for task in ('leaf-classification','spaceship-titanic'):
            directory=temp/task;(directory/'data').mkdir(parents=True)
            if task=='leaf-classification':
                train=pd.DataFrame({'id':range(60),'species':['a','b','c']*20,'x':range(60),'y':[.1,.3,.5]*20})
                test=train.drop(columns='species').iloc[:7].copy()
            else:
                train=pd.DataFrame({'PassengerId':[str(i) for i in range(60)],'Name':['name']*60,'Transported':[True,False]*30,
                    'Cabin':['a',None,'b']*20,'Age':range(60),'CryoSleep':[True,None,False]*20})
                test=train.drop(columns='Transported').iloc[:7].copy()
            train.to_csv(directory/'data/train.csv',index=False);test.to_csv(directory/'data/test.csv',index=False)
            (directory/'baseline.py').write_text(code_for(task))
            result=subprocess.run([sys.executable,'-B','baseline.py'],cwd=directory,capture_output=True,timeout=60)
            if result.returncode:raise RuntimeError('synthetic baseline execution failed: '+result.stderr.decode()[-1200:])
            out=pd.read_csv(directory/'submission.csv')
            if len(out)!=7:raise ValueError('row count')
            if task=='leaf-classification':
                assert list(out)==['id','a','b','c'] and np.allclose(out[['a','b','c']].sum(axis=1),1)
            else:assert list(out)==['PassengerId','Transported'] and set(out.Transported)<=set((True,False))
            records.append(dict(task=task,code_sha256=digest(task),synthetic_rows=7))
        prepared=read(root/'prepared.json');checks=[]
        for arm in ('uniform_random','critic_topk_random'):
            row=next(r for r in prepared['run_configs'] if r['arm']==arm)
            cfg=copy.deepcopy(read(root/'configs'/(row['run_id']+'.json'))['solver'])
            cfg['checkpoint_path']=str(temp/arm)
            c=NS(**cfg);node=MCTSNode(code='',parents=[]);journal=Journal();journal.append(node)
            s=NS(cfg=c,state=NS(current_step=1,running_time=0.),task_name='leaf-classification',task_desc='fixture',
                data_preview='fixture',journal=journal,journal_for_unselected=Journal(),global_min_q_val=0.,global_max_q_val=1.,
                critic_top_k=2,num_children_to_choose=1,remaining_steps=63)
            counters=dict(generation=0,rank=0,execution=0)
            async def generate(*args):
                counters['generation']+=1
                return MCTSNode(code='print(1)',parents=[],operators_used=['fixture'],operators_metrics=[])
            async def rank(*args):counters['rank']+=1;return [1.,2.,3.,4.]
            def parse(node,eval_result):node.is_buggy=False;node.metric=NS(value=.5,info={},maximize=True)
            s._draft=s._improve=generate;s.parse_eval_result=parse;s.log_journal=lambda:None
            s._backprop_step=lambda *args,**kw:None;s.set_global_q_values=lambda v:None
            def step(state,code):
                counters['execution']+=1
                output=ExecutionResult.get_empty();output.exit_code=0;output.timed_out=False;output.exec_time=.01
                return state,{EXECUTION_OUTPUT:output}
            state={'solver_interpreter':NS(timeout=300)}
            with patch('dojo.solvers.fore_ts.batch_runtime.rank_pool',side_effect=rank):
                expand_batch(s,[node],state,NS(step_task=step),MCTSNode,extract_code,cfg)
                assert counters==dict(generation=0,rank=0,execution=1)
                first_path=Path(c.checkpoint_path)/'forets-candidates-private/batch-1.sqlite'
                with sqlite3.connect(first_path) as db:first=json.loads(db.execute('select payload from snapshot').fetchone()[0])
                assert len(first['candidates'])==1 and not first['llm_requests']
                assert first['binding']['common_start']['code_sha256']==digest('leaf-classification')
                assert first['task_calls'][0]['intent']['code_sha256']==digest('leaf-classification')
                child=journal.nodes[-1]
                expand_batch(s,[node,child],state,NS(step_task=step),MCTSNode,extract_code,cfg)
                assert counters==dict(generation=4,rank=int(arm=='critic_topk_random'),execution=2)
            checks.append(dict(arm=arm,**counters,first_generation_calls=0,first_ranking_calls=0))
    result=dict(status='PASS_SYNTHETIC_NOT_REAL_TASK_RESULT',source_tree=read(root/'build.json')['source_tree'],
        baseline_programs=records,actual_batch_paths=checks,api_requests=0,gpu_dispatches=0)
    write(root/'common-start-integration.json',encode(result));print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root)
