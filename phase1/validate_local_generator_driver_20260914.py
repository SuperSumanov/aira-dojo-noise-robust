"""Exercise the prepared driver's native draft function without network or GPU."""
import asyncio,hashlib,json,logging,os,sys,tempfile,types
from pathlib import Path
from unittest.mock import patch
BASE=Path('/research/d7/spc/yzyang4')
ASSETS=BASE/'local-qwen27b-20260914-zcx1k1dy'
sys.path[:0]=[str(ASSETS/'integration-v3'),str(ASSETS/'source/src')]
import local_generator_runtime_20260914 as runtime

def main():
    os.umask(0o077);runtime.check_files()
    os.environ.update(PYTHON_DOTENV_DISABLED='1',LOGGING_DIR=str(ASSETS),MLE_BENCH_DATA_DIR=str(BASE/'mle-bench-data'),
      SUPERIMAGE_DIR=str(BASE/'aira-dojo/build/superimage'),DEFAULT_SLURM_PARTITION='gpu_24h',DEFAULT_SLURM_ACCOUNT='gpu',
      DEFAULT_SLURM_QOS='gpu',PRIMARY_KEY_QWEN3_8_27B='synthetic-driver-only',HARDWARE='one NVIDIA RTX 3090 (24 GiB), six CPU cores',
      LITELLM_LOCAL_MODEL_COST_MAP='True',NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    for k in ('PRIMARY_KEY','OPENROUTER_API_KEY','FORETS_RUN_BUDGET_PATH','FORETS_PAID_SCOPE'):os.environ.pop(k,None)
    logging.disable(logging.CRITICAL)
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    calls=[]
    async def complete(**kw):
        assert kw['base_url']=='http://127.0.0.1:8000/v1'
        assert kw['model']=='openai/qwen3.8-27b' and kw['api_key']=='synthetic-driver-only'
        assert kw['max_tokens']==32768 and kw['seed']==49
        assert kw['request_timeout'].read==1200 and kw['num_retries']==kw['max_retries']==0
        assert kw['extra_body']=={'chat_template_kwargs':{'enable_thinking':True}}
        assert 'CPU_DRIVER_PREVIEW' in kw['messages'][1]['content']
        calls.append(hashlib.sha256(json.dumps(kw['messages'],sort_keys=True).encode()).hexdigest())
        await asyncio.sleep(.01)
        choice=types.SimpleNamespace(message=types.SimpleNamespace(content='```python\nprint("LOCAL_RUNTIME_FIXTURE")\n```'),finish_reason='stop')
        return types.SimpleNamespace(choices=[choice],to_dict=lambda:{'usage':{'prompt_tokens':20,'completion_tokens':8}})
    cases=runtime.read(ASSETS/'calibration-inputs.json')['cases']
    with tempfile.TemporaryDirectory(prefix='generator-driver-cpu-',dir=ASSETS) as folder:
        async def execute():
            with patch.object(runtime,'ROOT',Path(folder)),patch.object(backend,'completion_fn',complete):
                return await asyncio.gather(*(runtime.generate_one(case,'CPU_DRIVER_PREVIEW') for case in cases))
        rows=asyncio.run(execute())
        assert len(calls)==len(rows)==2
        assert all(r['status']=='code_ready' and r['finish_reason']=='stop' and r['prompt_tokens']==20 and r['completion_tokens']==8 for r in rows)
        assert len(list(Path(folder).glob('code-*.private.py')))==2
    value=dict(status='PASS_PREPARED_DRIVER_MOCK_TRANSPORT_ONLY',utc=runtime.utc(),native_draft_calls=2,
        actual_model_calls=0,task_executions=0,gpu_jobs=0,prompt_sha256=calls,prepared_sha256=runtime.sha(ASSETS/'integration-v3/prepared.json'))
    runtime.write(ASSETS/'integration-v3/driver-cpu.json',value)
    print(json.dumps(value),flush=True)

if __name__=='__main__':main()
