"""One real free-route request using public artificial input, no corpus/GPU.

Raw headers, credential, response text and reasoning never leave remote memory.
Outputs contain only account/readiness metadata and bounded request usage.
"""
import argparse
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import datetime
import io
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHON_DOTENV_DISABLED='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        LOGGING_DIR=str(args.output), MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0,str(args.code))
    from forets_e2e_campaign import install_process_credential
    from forets_e2e_package import SOURCE, CLIENT, write_new
    from forets_pilot_plan import FREE_CLIENTS
    install_process_credential()
    credential=os.environ.get('OPENROUTER_API_KEY')
    if not credential:
        raise RuntimeError('remote credential is missing')
    os.environ['PRIMARY_KEY']=credential
    sys.path.insert(0,str(SOURCE/'src'))
    result=dict(status='NOT_READY', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        model=FREE_CLIENTS[CLIENT], generation_request_cap=1, timeout_seconds=120,
        max_output_tokens=8192, generation_attempts=0, gpu_jobs=0, task_runs=0,
        public_artificial_input_only=True, protected_data_read=False)
    write_new(args.output/'started.json',result)
    stage='account_metadata'
    budget=None
    # Suppress SDK diagnostics, which can include headers or provider output.
    # They are kept only in memory, never exported or saved as a raw log.
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        try:
            import httpx
            with httpx.Client(timeout=30,follow_redirects=False) as client:
                account=client.get('https://openrouter.ai/api/v1/key',
                                   headers={'Authorization':'Bearer '+credential})
                result['account_http_status']=account.status_code
                if account.status_code!=200:
                    raise RuntimeError('credential validation failed')
                data=account.json().get('data',{})
                result['account']={k:data.get(k) for k in
                    ('is_free_tier','limit','limit_remaining','usage','usage_daily','usage_monthly')}
                catalog=client.get('https://openrouter.ai/api/v1/models')
                result['catalog_http_status']=catalog.status_code
                catalog.raise_for_status()
                candidates=[m for m in catalog.json().get('data',[]) if m.get('id')==result['model']]
                if len(candidates)!=1:
                    result['model_available']=False
                    raise RuntimeError('fixed free model absent from current catalog')
                entry=candidates[0];result['model_available']=True
                result['pricing']=entry.get('pricing',{})
                result['supported_parameters']=entry.get('supported_parameters',[])
                for field in ('prompt','completion'):
                    if float(result['pricing'].get(field,'nan'))!=0.:
                        raise RuntimeError('fixed route is not free in current catalog')
                if not {'tools','tool_choice'} <= set(result['supported_parameters']):
                    raise RuntimeError('fixed route does not advertise required tool parameters')
            stage='bounded_generation'
            from dojo.config_dataclasses.run import RunConfig
            from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
            from dojo.core.solvers.llm_helpers.backends import lite_llm as backend
            from dojo.utils.run_budget import initialize
            manifest=json.loads((args.package/'manifest.json').read_text())
            cfg=RunConfig.load_from_json(args.package/'configs'/(manifest['runs'][0]['run_id']+'.json'))
            budget=Path(tempfile.mkdtemp(prefix='forets-live-route-',dir='/tmp'))/'attempts.sqlite'
            initialize(budget,1,8192)
            os.environ['FORETS_RUN_BUDGET_PATH']=str(budget)
            llm=GenericLLM(cfg.solver.operators['draft'])
            real_completion=backend.completion_fn
            async def observed_completion(**kwargs):
                try:
                    completion=await real_completion(**kwargs)
                    choices=completion.choices
                    result['response_structure']=dict(choice_count=len(choices),
                        finish_reason=choices[0].finish_reason if choices else None,
                        tool_call_count=len(choices[0].message.tool_calls or []) if choices else None)
                    return completion
                except Exception as exc:
                    result['transport_error_type']=type(exc).__name__
                    status=getattr(exc,'status_code',None)
                    result['transport_http_status']=status if type(status) is int else None
                    # Only an error summary, never response text/reasoning/headers.
                    message=str(exc).replace(credential,'[redacted]')
                    message=re.sub(r'(?i)(?:sk-[a-z0-9_.-]{12,}|Bearer\s+\S+)', '[redacted]',message)
                    result['transport_error_summary']=message[:300]
                    raise
            backend.completion_fn=observed_completion
            started=time.monotonic()
            result['generation_attempts']=1
            schema=json.dumps(dict(type='object',required=['code'],
                properties=dict(code=dict(type='string')),additionalProperties=False))
            response,info=asyncio.run(llm(
                messages=[dict(role='user',content='Public artificial connectivity check. Call emit with code exactly print(1). No other text is needed.')],
                json_schema=schema,function_name='emit',function_description='Return artificial test code.'))
            result['elapsed_seconds']=time.monotonic()-started
            usage=info.get('usage',{})
            result['usage']={k:usage.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens','cost','structured_output_transport')}
            result['parsed_public_fixture']=isinstance(response,dict) and response.get('code','').strip()=='print(1)'
            result['status']='READY' if result['parsed_public_fixture'] else 'PUBLIC_FIXTURE_NOT_MATCHED'
        except Exception as exc:
            result.update(status='NOT_READY',failure_stage=stage,error_type=type(exc).__name__)
            if re.fullmatch(r'bounded API attempt failed: [A-Za-z]+',str(exc)):
                result['adapter_error']=str(exc)
    # Read the reservation count, never request bodies or response reasoning.
    if budget is not None and budget.exists():
        import sqlite3
        with sqlite3.connect(budget.as_uri()+'?mode=ro',uri=True) as db:
            result['reserved_attempts']=db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
    write_new(args.output/'finished.json',result)
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['status']=='READY' else 1)


if __name__=='__main__':main()
