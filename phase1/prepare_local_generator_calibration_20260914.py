"""Prepare two new development drafts through native operators; no real transport.

This is NOT a GPU launcher, a search result, or a critic acceptance test.
Only old development CONFIGS and public task descriptions are reused.
"""
import asyncio
import copy
import hashlib
import json
import logging
import os
from pathlib import Path
import random
import re
import sys
import tarfile
import types
from unittest.mock import patch

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'local-qwen27b-20260914-zcx1k1dy'
DONOR=BASE/'forets-wallclock-20260912-km65uuej/configs'
SOURCE_SHA='c1206c13df05d9ab6b73119aabfb75820e90807e55a76f9f288f5d305a769291'
CASES=(('leaf-classification','00-leaf-classification-s46-uniform.json'),
       ('spaceship-titanic','05-spaceship-titanic-s46-uniform.json'))
SECRET=re.compile(rb'(?i)(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(raw):return hashlib.sha256(raw).hexdigest()

def checked(path):
    if path.is_symlink():raise ValueError('unexpected symlink')
    raw=path.read_bytes()
    if SECRET.search(raw):raise ValueError('credential shape: content withheld')
    return raw

def save(path,value):
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    if SECRET.search(raw):raise ValueError('output credential shape')
    with path.open('xb') as f:f.write(raw)
    return sha(raw)

def main():
    os.umask(0o077)
    if ROOT.resolve(strict=True)!=ROOT:raise ValueError('root scope')
    if sha((ROOT/'source.tar').read_bytes())!=SOURCE_SHA:raise ValueError('source archive drift')
    with tarfile.open(ROOT/'source.tar') as bundle:
        for member in bundle.getmembers():
            name=Path(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir()):
                raise ValueError('archive entry')
            if member.isfile() and (ROOT/'source'/name).read_bytes()!=bundle.extractfile(member).read():
                raise ValueError('native source changed')
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR=str(ROOT),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
        SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        PRIMARY_KEY_QWEN3_8_27B='synthetic-local-integration-fixture',
        HARDWARE='one NVIDIA RTX 3090 (24 GiB), six CPU cores',
        NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    for key in ('PRIMARY_KEY','OPENROUTER_API_KEY','FORETS_RUN_BUDGET_PATH','FORETS_PAID_SCOPE'):
        os.environ.pop(key,None)
    sys.path.insert(0,str(ROOT/'source/src'))
    logging.disable(logging.CRITICAL)
    import numpy as np
    from omegaconf import OmegaConf
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    from dojo.core.solvers.operators.draft import draft_op
    from dojo.core.solvers.utils.response import extract_code
    from dojo.core.solvers.utils.journal import Journal
    cases=[]
    for index,(task,filename) in enumerate(CASES):
        raw=checked(DONOR/filename);prior=json.loads(raw)
        operator=copy.deepcopy(prior['solver']['operators']['draft'])
        operator['llm']['client']=dict(api='litellm',model_id='qwen3.8-27b',
            base_url='http://127.0.0.1:8000/v1',provider='selfhosted',use_azure_client=False)
        operator['llm']['generation_kwargs']=dict(bounded_transport=True,bounded_max_attempts=1,
            bounded_request_timeout_seconds=1200,max_tokens=32768,temperature=.6,top_p=.95,seed=49,
            extra_body={'chat_template_kwargs':{'enable_thinking':True}},structured_output_retries=0)
        description=checked(BASE/'mle-bench-data'/task/'prepared/public/description.md')
        interpreter=copy.deepcopy(prior['interpreter'])
        interpreter['working_dir']=str(ROOT/f'calibration-work-{index}')
        interpreter['timeout']=300
        cases.append(dict(index=index,task=task,seed=49,operator=operator,interpreter=interpreter,
            public_data_dir=str(BASE/'mle-bench-data'/task/'prepared/public'),
            description=description.decode(),description_sha256=sha(description),donor_config_sha256=sha(raw),
            solver_draft=dict(available_packages=prior['solver']['available_packages'],
                execution_timeout=300,step_limit=1,data_preview=True)))
    calls=[]
    async def complete(**kwargs):
        assert kwargs['model']=='openai/qwen3.8-27b'
        assert kwargs['base_url']=='http://127.0.0.1:8000/v1'
        assert kwargs['request_timeout'].read==1200
        assert kwargs['max_retries']==kwargs['num_retries']==0
        assert kwargs['max_tokens']==32768 and kwargs['seed']==49
        assert kwargs['extra_body']=={'chat_template_kwargs':{'enable_thinking':True}}
        messages=kwargs['messages']
        assert len(messages)==2 and '300 seconds' in messages[0]['content']
        assert 'CPU_FIXTURE_DATA_PREVIEW' in messages[1]['content']
        calls.append(dict(prompt_sha256=sha(json.dumps(messages,sort_keys=True).encode()),
                          prompt_chars=sum(len(m['content']) for m in messages),seed=kwargs['seed']))
        choice=types.SimpleNamespace(message=types.SimpleNamespace(content='```python\npass\n```'),finish_reason='stop')
        return types.SimpleNamespace(choices=[choice],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
    async def verify():
        with patch.object(generic,'get_logger',lambda:None),patch.object(backend,'completion_fn',complete):
            for case in cases:
                random.seed(case['seed']);np.random.seed(case['seed'])
                output,info=await draft_op(generic.GenericLLM(OmegaConf.create(case['operator'])),
                    OmegaConf.create(case['solver_draft']),None,case['description'],Journal(),0,1800,
                    data_preview='CPU_FIXTURE_DATA_PREVIEW')
                assert extract_code(output).strip()=='pass'
                assert info['usage']['finish_reason']=='stop'
                assert info['usage']['cost_status']=='local_api_no_charge_excludes_gpu'
    asyncio.run(verify())
    if len(calls)!=2:raise ValueError('both native draft paths required')
    inputs_sha=save(ROOT/'calibration-inputs.json',dict(source_sha256=SOURCE_SHA,cases=cases,
        new_development_only=True,old_runs_not_reexecuted=True,service_inference_not_enabled=True))
    result=dict(status='PASS_TWO_NATIVE_TASK_DRAFTS_MOCK_TRANSPORT_ONLY',calls=calls,
        source_sha256=SOURCE_SHA,calibration_inputs_sha256=inputs_sha,task_count=len(cases),
        real_data_preview_not_yet_run=True,real_generation_and_execution_not_yet_run=True,
        gpu_jobs=0,actual_api_calls=0,model_fits=0)
    save(ROOT/'calibration-cpu.json',result)
    print(json.dumps(result))

if __name__=='__main__':main()
