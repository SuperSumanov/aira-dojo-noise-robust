"""Real native GenericLLM -> LiteLLM integration with a replaced transport only."""
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tarfile
import types
from unittest.mock import patch

ROOT=Path('/research/d7/spc/yzyang4/local-qwen27b-20260914-zcx1k1dy')
SHA='c1206c13df05d9ab6b73119aabfb75820e90807e55a76f9f288f5d305a769291'

def main():
    os.umask(0o077)
    raw=(ROOT/'source.tar').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA:
        raise ValueError('source artifact drift')
    source=ROOT/'source'
    new_source=not source.exists()
    source.mkdir(exist_ok=True)
    with tarfile.open(ROOT/'source.tar') as bundle:
        for member in bundle.getmembers():
            path=Path(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isdir() or member.isfile()):
                raise ValueError('unexpected source archive member')
        if new_source:
            bundle.extractall(source,filter='data')
        else:
            for member in bundle.getmembers():
                if member.isfile():
                    path=source/member.name
                    if path.is_symlink() or path.read_bytes()!=bundle.extractfile(member).read():
                        raise ValueError('existing source changed; no overwrite')
    sys.path.insert(0,str(source/'src'))
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR=str(ROOT),MLE_BENCH_DATA_DIR='/research/d7/spc/yzyang4/mle-bench-data',
        SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',
        DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',DEFAULT_SLURM_QOS='gpu',
        PRIMARY_KEY_QWEN3_8_27B='synthetic-local-integration-fixture',PRIMARY_KEY='synthetic-global-integration-fixture',
        NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    for key in ('FORETS_RUN_BUDGET_PATH','FORETS_PAID_SCOPE','OPENROUTER_API_KEY'):
        os.environ.pop(key,None)
    logging.disable(logging.CRITICAL)
    from omegaconf import OmegaConf
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    def prompt(template, variables):
        return dict(template=template,input_variables=variables,partial_variables={})
    config=OmegaConf.create(dict(llm=dict(client=dict(api='litellm',model_id='qwen3.8-27b',base_url='http://127.0.0.1:8000/v1',provider='selfhosted',use_azure_client=False),
        generation_kwargs=dict(bounded_transport=True,bounded_request_timeout_seconds=1200,bounded_max_attempts=1,max_tokens=32768,temperature=.6,seed=20260914)),
        system_message_prompt_template=prompt('You are a careful assistant.',[]),
        init_user_message_prompt_template=prompt('{{ task_desc }}',['task_desc']),
        user_message_prompt_template=prompt('{{ task_desc }}',['task_desc'])))
    calls=[]
    async def complete(**kwargs):
        assert kwargs['base_url']=='http://127.0.0.1:8000/v1'
        assert kwargs['model']=='openai/qwen3.8-27b'
        assert kwargs['api_key']=='synthetic-local-integration-fixture'
        assert kwargs['max_retries']==kwargs['num_retries']==0
        assert kwargs['max_tokens']==32768
        assert kwargs['request_timeout'].read==1200
        structured=kwargs.get('response_format')=={'type':'json_object'}
        calls.append(dict(structured=structured,max_tokens=kwargs['max_tokens'],model=kwargs['model']))
        output='{"ready":true}' if structured else 'LOCAL_NATIVE_FIXTURE'
        choice=types.SimpleNamespace(message=types.SimpleNamespace(content=output),finish_reason='stop')
        return types.SimpleNamespace(choices=[choice],to_dict=lambda:{'usage':{'prompt_tokens':12,'completion_tokens':5}})
    async def run():
        with patch.object(generic,'get_logger',lambda:None),patch.object(backend,'completion_fn',complete):
            llm=generic.GenericLLM(config)
            text,info=await llm(query_data={'task_desc':'CPU integration fixture, no benchmark data'})
            assert text=='LOCAL_NATIVE_FIXTURE' and info['usage']['finish_reason']=='stop'
            obj,details=await llm(query_data={'task_desc':'Return readiness'},json_schema=json.dumps({'type':'object','properties':{'ready':{'type':'boolean'}},'required':['ready'],'additionalProperties':False}),
                function_name='local_readiness',function_description='Return a readiness flag')
            assert obj=={'ready':True}
            assert details['usage']['cost_status']=='local_api_no_charge_excludes_gpu'
            assert len(calls)==2
    asyncio.run(run())
    result=dict(status='PASS_NATIVE_CLIENT_WITH_MOCK_TRANSPORT_ONLY',source_sha256=SHA,
        cases=calls,actual_api_calls=0,gpu_jobs=0,model_inference=False,production_factory_and_generic_llm_used=True,
        real_service_not_yet_verified=True)
    with (ROOT/'native-client-cpu.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps(result))

if __name__=='__main__':main()
