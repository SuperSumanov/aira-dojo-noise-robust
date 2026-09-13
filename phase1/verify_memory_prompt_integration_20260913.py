"""Actual operator -> GenericLLM -> rendered request, with transport replaced."""
import asyncio
import copy
import inspect
import json
import logging
import os
from pathlib import Path
import random
import sys
from types import SimpleNamespace as NS
from unittest.mock import patch
from forets_environment_build_20260912 import read,write,encode,sha
from forets_execution_memory_20260913 import OPERATORS,HEADER,TEXT_SHA

def run(root):
    artifact=read(root/'artifact.json');prepared=read(root/'prepared.json');memory=read(root/'frozen-memory.json')
    if sha(memory['text'].encode())!=TEXT_SHA:raise ValueError('frozen prior memory')
    for name,digest in artifact['source_files'].items():
        if sha((root/'source'/name).read_bytes())!=digest:raise ValueError('actual source drift')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',LOGGING_DIR=str(root),
        MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu')
    sys.path[:0]=[str(root/'source/src'),str(root/'code')];logging.disable(logging.CRITICAL)
    from dojo.config_dataclasses.run import RunConfig
    from dojo.core.solvers.llm_helpers import generic_llm as gl
    from dojo.core.solvers.operators.draft import draft_op
    from dojo.core.solvers.operators.improve import improve_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.utils.journal import Journal
    captured={};rows=[]
    async def execute(planned,operator):
        cfg=RunConfig.from_dict(read(root/'configs'/(planned['run_id']+'.json'),planned['config_sha256'])).solver
        snapshots=[]
        async def transport(client,messages,**kwargs):
            snapshots.append(copy.deepcopy(dict(messages=messages,kwargs=kwargs)))
            return 'print(1)',{}
        random.seed(planned['seed'])
        with patch.object(gl,'get_client',return_value=NS(client_content_key='content')),patch.object(gl,'audited_query',transport):
            llm=gl.GenericLLM(cfg.operators[operator])
            args=dict(task_description='Synthetic CPU integration task; no real task data.',journal=Journal(),
                step_count=2,remaining_time=550,data_preview='Synthetic columns only')
            node=NS(code='print(0)',term_out='synthetic prior execution')
            if operator=='draft':result=draft_op(llm,cfg,None,**args)
            elif operator=='improve':result=improve_op(llm,cfg,None,input_node=node,**args)
            else:result=debug_op(llm,cfg,None,input_node=node,**args)
            if inspect.isawaitable(result):await result
        if len(snapshots)!=1:raise ValueError('one actual rendered request')
        value=snapshots[0];messages=value['messages']
        if len(messages)!=2 or messages[0]['role']!='system':raise ValueError('actual initial prompt path')
        enabled=planned['arm']=='execution_memory'
        if enabled:
            if messages[0]['content'].count(HEADER)!=1 or not messages[0]['content'].endswith('\n\n'+memory['text']):
                raise ValueError('memory not reaching actual request')
        elif HEADER in json.dumps(value):raise ValueError('control memory leakage')
        normalized=copy.deepcopy(value)
        if enabled:normalized['messages'][0]['content']=normalized['messages'][0]['content'][:-len('\n\n'+memory['text'])]
        key=(planned['task'],planned['seed'],operator)
        if key in captured and captured[key]!=normalized:raise ValueError('rendered pair differs beyond frozen memory')
        captured[key]=normalized
        rows.append(dict(run_id=planned['run_id'],operator=operator,memory_enabled=enabled,request_sha256=sha(encode(value)),
            normalized_sha256=sha(encode(normalized))))
    for planned in prepared['run_configs']:
        for operator in OPERATORS:asyncio.run(execute(planned,operator))
    if len(rows)!=24 or len(captured)!=12:raise ValueError('all actual operators and paired configurations required')
    result=dict(status='CPU_ACTUAL_OPERATOR_PROMPTS_NOT_EFFICACY',source_tree=artifact['source_tree'],actual_operator_calls=24,
        only_frozen_memory_differs=True,memory_text_sha256=TEXT_SHA,rows=rows,api_requests=0,gpu_jobs=0,
        inspector_sha256=sha(Path(__file__).read_bytes()))
    print(json.dumps(dict(status=result['status'],actual_operator_calls=24,sha256=write(root/'memory-prompt-integration.json',encode(result)))))

if __name__=='__main__':run(Path(sys.argv[1]).resolve(strict=True))
