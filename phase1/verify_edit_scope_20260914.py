"""Actual-source operator integration and synthetic common-start equivalence."""
import argparse
import ast
import asyncio
import copy
import json
import logging
import os
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_environment_build_20260912 import read, write, encode, sha


def run(root):
    info=read(root/'artifact.json');prepared=read(root/'prepared.json')
    for n,h in info['source_files'].items():
        if sha((root/'source'/n).read_bytes())!=h:raise ValueError('source drift')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')];logging.disable(logging.CRITICAL)
    from dojo.config_dataclasses.run import RunConfig
    from dojo.core.solvers.llm_helpers import generic_llm as gl
    from dojo.core.solvers.utils.journal import Journal
    from dojo.solvers.fore_ts.fore_ts import ForeTS
    from dojo.solvers.mcts.mcts import MCTSNode
    from dojo.solvers.fore_ts import edit_scope as es, common_start
    from dojo.core.solvers.utils.response import extract_code
    from dojo.core.solvers.operators import improve,debug,draft
    import functools
    from build_edit_scope_20260914 import order,normalized_template
    from forets_e2e_package import common_config
    if [(r['block'],r['task'],r['seed'],r['arm']) for r in prepared['run_configs']]!=order():raise ValueError('matrix')
    captured={};rows=[];normalized=[]
    for r in prepared['run_configs']:
        raw=read(root/'configs'/(r['run_id']+'.json'),r['config_sha256']);cfg=RunConfig.from_dict(raw).solver
        if cfg.time_limit_secs!=1200 or cfg.execution_timeout!=300 or cfg.num_children!=2 or cfg.num_children_to_choose!=2:
            raise ValueError('fixed compute config')
        normalized.append(normalized_template(raw,r['run_id'],root,common_config))
        solver=ForeTS.__new__(ForeTS);solver.cfg=cfg;solver.task_name=r['task'];solver.task_desc='Synthetic integration task'
        solver.journal=Journal();solver.state=NS(current_step=2,running_time=30);solver.data_preview=None;solver.root_node=None
        solver.logger=NS(info=lambda *a:None)
        parent=MCTSNode(code=common_start.canonical(r['task']),parents=[]);parent._term_out=['synthetic prior output']
        for op,fn in [('draft',draft.draft_op),('improve',improve.improve_op),('debug',debug.debug_op)]:
            snapshots=[]
            async def transport(client,messages,**kwargs):
                snapshots.append(copy.deepcopy(dict(messages=messages,kwargs=kwargs)))
                return 'Plan: synthetic fixture.\n```python\ndef build_model(X):\n    return 123\n```', {'fixture':1}
            random.seed(r['seed'])
            with patch.object(gl,'get_client',return_value=NS(client_content_key='content')),patch.object(gl,'audited_query',transport):
                llm=gl.GenericLLM(cfg.operators[op]);setattr(solver,op+'_fn',functools.partial(fn,llm,cfg,None))
                node=solver._debug(parent) if op=='debug' else asyncio.run(solver._draft(parent) if op=='draft' else solver._improve(parent))
            if len(snapshots)!=1:raise ValueError('one native operator request')
            val=snapshots[0];messages=val['messages'];suffix='\n\n'+es.HEADER+'\n'+es.INSTRUCTION
            if r['arm']=='model_module':
                if not messages[0]['content'].endswith(suffix):raise ValueError('module prompt not reaching transport')
                messages[0]['content']=messages[0]['content'][:-len(suffix)]
                if not node.operators_metrics[0]['edit_scope']['interface_accepted']:raise ValueError('module rejected')
                tree=ast.parse(node.code)
                if sum(isinstance(n,ast.FunctionDef) and n.name=='build_model' for n in tree.body)!=1 or len(tree.body)<5:
                    raise ValueError('module not assembled into real program')
                expected,_=es.assemble(common_start.canonical(r['task']),extract_code('def build_model(X):\n return 123'))
                if ast.dump(ast.parse(expected))!=ast.dump(tree):raise ValueError('actual native result differs')
            elif es.HEADER in json.dumps(val) or 'edit_scope' in node.operators_metrics[0]:raise ValueError('control changed')
            key=(r['task'],r['seed'],op)
            if key in captured and captured[key]!=val:raise ValueError('request differs beyond interface')
            captured[key]=val;rows.append(dict(run_id=r['run_id'],operator=op,output_sha256=sha(node.code.encode())))
    if any(normalized[i]!=normalized[i+1] for i in range(0,16,2)):raise ValueError('config pair changes extra variable')
    # Run the unchanged and refactored common start on generated, labeled CPU
    # fixtures. No real task data or protected corpus is touched.
    import numpy as np
    import pandas as pd
    from contextlib import redirect_stdout
    import io
    eq=[]
    with tempfile.TemporaryDirectory(prefix='edit-start-equivalence-',dir=root) as temp:
        old_cwd=Path.cwd();os.chdir(temp)
        try:
            Path('data').mkdir();rng=np.random.default_rng(11)
            for task in ('leaf-classification','spaceship-titanic'):
                if task=='leaf-classification':
                    frame=pd.DataFrame(rng.normal(size=(120,4)),columns=['f1','f2','f3','f4']);frame.insert(0,'id',range(120));frame['species']=np.tile(['a','b','c'],40)
                    test=frame.drop(columns='species').iloc[:17].copy()
                else:
                    frame=pd.DataFrame({'PassengerId':[str(i) for i in range(120)],'Name':['n']*120,
                        'HomePlanet':np.tile(['Earth','Mars',None],40),'CryoSleep':np.tile([True,False,None],40),
                        'Age':rng.normal(size=120),'Transported':np.tile([True,False],60)})
                    test=frame.drop(columns='Transported').iloc[:17].copy()
                frame.to_csv('data/train.csv',index=False);test.to_csv('data/test.csv',index=False)
                results=[]
                for code in (common_start.original_code_for(task),common_start.code_for(task)):
                    with redirect_stdout(io.StringIO()) as out: exec(compile(code,'<synthetic-shared-start>','exec'),{})
                    results.append((Path('submission.csv').read_bytes(),out.getvalue()))
                if results[0]!=results[1]:raise ValueError('refactor changes baseline outputs')
                eq.append(dict(task=task,identical_submission_and_validation=True))
        finally:os.chdir(old_cwd)
    result=dict(status='PASSED_ACTUAL_OPERATOR_AND_SHARED_START_CPU',source_tree=info['source_tree'],actual_operator_calls=len(rows),
        config_pairs=8,only_interface_differs=True,initial_equivalence=eq,rows=rows,api_calls=0,gpu_jobs=0)
    print(json.dumps(dict(status=result['status'],operators=len(rows),sha256=write(root/'edit-scope-integration.json',encode(result)))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root.resolve(strict=True))
