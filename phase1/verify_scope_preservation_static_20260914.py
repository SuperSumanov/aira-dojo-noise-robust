"""Actual-source prompt/operator wiring without building a paid successor."""
import asyncio
import copy
import functools
import json
import logging
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_environment_build_20260912 import read,sha
from forets_scope_preservation_20260914 import transform,strip_intervention,order,HEADER,INSTRUCTION
from forets_edit_scope_20260914 import HEADER as MODULE_HEADER,INSTRUCTION as MODULE_INSTRUCTION

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')

def main():
    art=read(ROOT/'artifact.json');prepared=read(ROOT/'prepared.json')
    if art['source_tree']!='8bb325fa167a9db54656dd6535ce1f3d69859c22':raise ValueError('current source')
    for n,h in art['source_files'].items():
        if sha((ROOT/'source'/n).read_bytes())!=h:raise ValueError('source changed')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(ROOT),
        MLE_BENCH_DATA_DIR=str(ROOT.parent/'mle-bench-data'),SUPERIMAGE_DIR=str(ROOT.parent/'aira-dojo/build/superimage'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(ROOT/'source/src'),str(ROOT/'code')];logging.disable(logging.CRITICAL)
    from dojo.config_dataclasses.run import RunConfig
    from dojo.core.solvers.llm_helpers import generic_llm as gl
    from dojo.core.solvers.utils.journal import Journal
    from dojo.solvers.fore_ts.fore_ts import ForeTS
    from dojo.solvers.mcts.mcts import MCTSNode
    from dojo.solvers.fore_ts import common_start
    from dojo.core.solvers.operators import improve,debug,draft
    import build_scope_preservation_20260914 as builder
    seen={};calls=0
    for block,task,seed,arm in order():
        row=next(r for r in prepared['run_configs'] if r['task']==task and r['arm']=='whole_program')
        base=read(ROOT/'configs'/(row['run_id']+'.json'),row['config_sha256'])
        base['metadata']['seed']=seed;base['solver']['selector_seed']=seed
        cfgraw=transform(base,arm);back=strip_intervention(cfgraw,arm)
        expected=copy.deepcopy(base);expected['solver'].pop('edit_scope')
        if back!=expected:raise ValueError('extra configuration changes')
        cfg=RunConfig.from_dict(cfgraw).solver
        solver=ForeTS.__new__(ForeTS);solver.cfg=cfg;solver.task_name=task;solver.task_desc='Synthetic wiring task'
        solver.journal=Journal();solver.state=NS(current_step=2,running_time=30);solver.data_preview=None;solver.root_node=None
        solver.logger=NS(info=lambda *a:None)
        parent=MCTSNode(code=common_start.canonical(task),parents=[]);parent._term_out=['synthetic prior output']
        for op,fn in [('draft',draft.draft_op),('improve',improve.improve_op),('debug',debug.debug_op)]:
            captured=[]
            async def transport(client,messages,**kwargs):
                captured.append(copy.deepcopy(dict(messages=messages,kwargs=kwargs)))
                return 'Plan: fixture.\n```python\ndef build_model(X):\n    return 123\n```',{'fixture':1}
            random.seed(seed)
            with patch.object(gl,'get_client',return_value=NS(client_content_key='content')),patch.object(gl,'audited_query',transport):
                llm=gl.GenericLLM(cfg.operators[op]);setattr(solver,op+'_fn',functools.partial(fn,llm,cfg,None))
                node=solver._debug(parent) if op=='debug' else asyncio.run(solver._draft(parent) if op=='draft' else solver._improve(parent))
            if len(captured)!=1:raise ValueError('one native transport call')
            val=captured[0];suffix=None
            if arm=='model_module':suffix='\n\n'+MODULE_HEADER+'\n'+MODULE_INSTRUCTION
            elif arm=='preserve_program':suffix='\n\n'+HEADER+'\n'+INSTRUCTION
            if suffix:
                if not val['messages'][0]['content'].endswith(suffix):raise ValueError('prompt delivery')
                val['messages'][0]['content']=val['messages'][0]['content'][:-len(suffix)]
            key=(task,seed,op)
            if key in seen and seen[key]!=val:raise ValueError('extra request changes')
            seen[key]=val;calls+=1
            has_scope='edit_scope' in node.operators_metrics[0]
            if has_scope!=(arm=='model_module'):raise ValueError('full-output control unexpectedly assembled')
    derived=[]
    for name in ('forets_block_controller_20260911.py','forets_native_run_20260911.py','forets_paid_route_20260911.py'):
        text=builder.derive(name,(ROOT/'code'/name).read_text());compile(text,name,'exec');derived.append(name)
    result=dict(status='PASS_ACTUAL_PRESERVATION_WIRING_NO_DISPATCH',actual_operator_calls=calls,configurations=12,
        only_interface_and_instruction_differ=True,derived_controllers=derived,api_calls=0,gpu_jobs=0,
        active_source_changed=False,script_sha256=sha(Path(__file__).read_bytes()),source_tree=art['source_tree'])
    print(json.dumps(result))

if __name__=='__main__':main()
