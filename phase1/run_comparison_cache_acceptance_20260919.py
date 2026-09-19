"""Original native analysis on every cached alternative, without external grades."""
import argparse,asyncio,copy,hashlib,json,math,os,random,re,shutil,subprocess,tempfile,time,types
from pathlib import Path
from unittest.mock import patch
import run_comparison_depth2_debug_20260919 as depth
first=depth.first;runtime=depth.runtime;BASE=depth.BASE
SCRIPT=Path(__file__).name
PLAN='comparison_cache_acceptance_plan_20260919.json'
BANKS={1:(BASE/'comparison-reuse-20260919-5m6jrtah','f3ea334c94257bbbbc06229a8a3aeea609e2516879bdf9a32822e176897ee9ce'),
       2:(BASE/'comparison-reuse-20260919-851fmp2v','54154a13de4d5dbcb34ba09a47adf24162382fd0818669fb914856dc6ce15ded')}

def configure(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'comparison-cache-acceptance-20260919-[a-z0-9_]+',root.name):raise ValueError('scope')
    runtime.ROOT=root;runtime.ATTEMPT_SECONDS=4200;return root

def inputs():
    from run_comparison_spooky_pool_20260919 import read,sha
    templates={case['seed']:case for case in depth.inputs()};cases=[]
    for seed,(root,digest) in BANKS.items():
        summary=read(root/'summary.json',digest)
        rows=[r for r in summary['rows'] if r['seed']==seed and r['role']=='cache']
        if len(rows)!=4:raise ValueError('complete four-cache bank')
        for row in rows:
            code=(root/'codes'/f'{row["index"]}.private.py').read_bytes()
            log=(root/f'output-{row["index"]}.private.log').read_bytes()
            if sha(code)!=row['code_sha256'] or runtime.SHAPES.search(code+log):raise ValueError('code/log identity/security')
            request_seed=801+len(cases);template=templates[seed]
            operator=copy.deepcopy(template['analysis_operator'])
            operator['llm']['generation_kwargs']['seed']=request_seed
            cases.append(dict(index=len(cases),seed=seed,request_seed=request_seed,run=row['run'],node=row['node'],
                code=code.decode(),term_out=log.decode(),code_sha256=sha(code),log_sha256=sha(log),
                exit_code=row['exit_code'],timed_out=row['timed_out'],description=template['description'],
                operator=operator,solver=template['solver'],source_summary_sha256=digest))
    return cases

async def request(case):
    import numpy as np
    from omegaconf import OmegaConf
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    from dojo.core.solvers.operators.analyze import analyze_op
    from dojo.core.solvers.utils.journal import Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    random.seed(case['request_seed']);np.random.seed(case['request_seed']);generic.get_logger=lambda:None
    node=Node(code=case['code'],plan='',parents=[],_term_out=[case['term_out']],exit_code=case['exit_code'],
        is_buggy=None,metric=WorstMetricValue())
    return await first.resolve(analyze_op(generic.GenericLLM(OmegaConf.create(copy.deepcopy(case['operator']))),
        OmegaConf.create(copy.deepcopy(case['solver'])),case['description'],node))

def cpu(root):
    first.setup(root)
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    calls=[];cases=runtime.read(root/'inputs.private.json')['cases']
    async def completion(**kwargs):
        case=cases[len(calls)];content='\n'.join(str(m.get('content','')) for m in kwargs['messages'])
        assert kwargs['seed']==case['request_seed'] and kwargs['request_timeout'].read==300
        assert kwargs['max_retries']==kwargs['num_retries']==0 and kwargs['response_format']=={'type':'json_object'}
        assert case['code'].strip() in content
        # Forbidden fields are absent from the allowlisted input, not merely
        # omitted by one particular prompt template.
        assert not set(case)&{'score','valid','independent_score','official_grade'}
        calls.append(dict(seed=kwargs['seed'],prompt_sha256=hashlib.sha256(content.encode()).hexdigest()))
        response=json.dumps(dict(is_bug=case['exit_code']!=0,summary='CPU mock',metric=.5 if case['exit_code']==0 else None))
        choice=types.SimpleNamespace(message=types.SimpleNamespace(content=response),finish_reason='stop')
        return types.SimpleNamespace(choices=[choice],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
    async def check():
        with patch.object(backend,'completion_fn',completion):
            for case in cases:
                response,_=await request(case);assert isinstance(response,dict)
    asyncio.run(check())
    if len(calls)!=8:raise ValueError('eight calls required')
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    runtime.write(root/'cpu.json',dict(status='PASS_EIGHT_NATIVE_ANALYSES',real_calls=0,calls=calls,prepared_sha256=runtime.sha(root/'prepared.json')))

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    cases=inputs();root=configure(Path(tempfile.mkdtemp(prefix='comparison-cache-acceptance-20260919-',dir=BASE)))
    for name in (SCRIPT,PLAN,'run_comparison_depth2_debug_20260919.py','run_comparison_live_debug_20260919.py','local_generator_runtime_20260914.py'):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'service_entry.py').write_text(runtime.SERVICE_ENTRY);(root/'service-cache/tmp').mkdir(parents=True)
    runtime.write(root/'inputs.private.json',dict(cases=cases))
    batch=f'''#!/bin/bash
#SBATCH --job-name=comparison-cache-acceptance
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=01:10:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 4130s {runtime.PYTHON} -B {root}/{SCRIPT} controller --root {root}
'''
    (root/'run.sbatch').write_text(batch)
    files={str(p.relative_to(root)):runtime.sha(p) for p in root.rglob('*') if p.is_file()}
    runtime.write(root/'prepared.json',dict(commit=commit,utc=runtime.utc(),files=files,
        model='cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4',revision='dc430725f831dd90d9271738b877879a46a82239',gpu_hours_cap=4200*2/3600))
    with (root/'.service.env').open('x') as handle:handle.write('PRIMARY_KEY_QWEN3_8_27B='+'0'*64+'\n')
    cpu(root);print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',root=str(root),prepared_sha256=runtime.sha(root/'prepared.json'))),flush=True)

def generate(root):
    first.setup(root);rows=[]
    async def calls():
        for case in runtime.read(root/'inputs.private.json')['cases']:
            started=time.monotonic();row={k:case[k] for k in ('index','seed','request_seed','run','node','code_sha256','log_sha256','exit_code','timed_out','source_summary_sha256')}
            try:
                response,info=await asyncio.wait_for(request(case),timeout=310)
                runtime.write(root/f'answer-{case["index"]}.private.json',dict(response=response,info=info))
                if not isinstance(response,dict) or type(response.get('is_bug')) is not bool:raise ValueError('analysis schema')
                metric=response.get('metric')
                if metric is not None and (type(metric) not in (int,float) or not math.isfinite(metric)):raise ValueError('finite metric')
                row.update(status='analysis_returned',native_is_bug=response['is_bug'],native_metric=metric,
                    would_accept_without_grader_guard=not response['is_bug'] and case['exit_code']==0 and not case['timed_out'] and metric is not None,
                    finish_reason=info['usage'].get('finish_reason'),prompt_tokens=info['usage'].get('prompt_tokens'),completion_tokens=info['usage'].get('completion_tokens'))
            except Exception as exc:row.update(status='analysis_unknown',error_type=type(exc).__name__)
            row['analysis_seconds']=time.monotonic()-started
            runtime.write(root/f'analysis-{case["index"]}.json',row);rows.append(row)
    asyncio.run(calls());runtime.write(root/'analysis-summary.json',dict(role='native_cache_analysis_without_external_scores',rows=rows,paid_api_calls=0,training=False))

def submit(root):
    p=runtime.check_files();runtime.asset_check(p)
    if runtime.read(root/'cpu.json')['prepared_sha256']!=runtime.sha(root/'prepared.json'):raise ValueError('preflight')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i|%j'],env=env,text=True,timeout=25).splitlines()
    if len(queue)>=4 or any(r.split('|')[0]=='14134' for r in queue):raise ValueError('wait for prior generator service to finish; job cap')
    with (root/'capacity.tmp').open('xb') as handle:os.posix_fallocate(handle.fileno(),0,2*1024**3)
    (root/'capacity.tmp').unlink()
    runtime.write(root/'submit-intent.json',dict(utc=runtime.utc(),gpu_hours_cap=p['gpu_hours_cap']))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
        '--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
    runtime.write(root/'launch.json',dict(job=job,utc=runtime.utc()))
    print(json.dumps(dict(status='SUBMITTED',root=str(root),job=job,gpu_hours_cap=p['gpu_hours_cap'])),flush=True)

if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('role',choices=['prepare','submit','controller','server']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');args=parser.parse_args()
    first.SCRIPT=SCRIPT;first.generate=generate
    if args.role=='prepare':prepare(args.commit)
    else:
        root=configure(args.root)
        if args.role=='server':runtime.server()
        elif args.role=='controller':first.controller(root,service_seconds=4080,closed_status='eight_analyses_closed')
        else:submit(root)
