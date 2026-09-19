"""Continue both fixed new debug failures through native analysis and repair."""
import argparse, asyncio, copy, hashlib, json, os, random, re, shutil, subprocess, tarfile, tempfile, time, types
from pathlib import Path, PurePosixPath
from unittest.mock import patch
import run_comparison_live_debug_20260919 as first

runtime=first.runtime
BASE=first.BASE
SCRIPT=Path(__file__).name
PLAN='comparison_depth2_debug_plan_20260919.json'
GEN=BASE/'comparison-live-debug-20260919-kksebq_4'
EXEC=BASE/'comparison-fresh-debug-exec-20260919-53mn3zh0'
SUMMARY='71302cc7321a42ec592f90a367738f935ec4ff60130fa8fb83ed79a317d7e86b'

def configure(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'comparison-depth2-debug-20260919-[a-z0-9_]+',root.name):raise ValueError('root scope')
    runtime.ROOT=root;runtime.ATTEMPT_SECONDS=4800
    return root

def inputs():
    from run_comparison_spooky_pool_20260919 import read,sha
    summary=read(EXEC/'summary.json',SUMMARY)
    if summary['job']!='14133' or summary['allocation_state']!='COMPLETED':raise ValueError('closed parent')
    cases=first.prefix_inputs();analyses={}
    with tarfile.open(first.ARCHIVE,'r|gz') as archive:
        for member in archive:
            p=PurePosixPath(member.name)
            if not member.isfile() or p.name!='dojo_config.json':continue
            run=sha(str(p.parent).encode())[:16]
            if run not in first.CONFIG_SHAS:continue
            raw=archive.extractfile(member).read()
            if sha(raw)!=first.CONFIG_SHAS[run] or runtime.SHAPES.search(raw):raise ValueError('original analysis config')
            analyses[run]=json.loads(raw)['solver']['operators']['analyze']
    for case in cases:
        row,=[r for r in summary['rows'] if r['seed']==case['seed']]
        if row['execution_status']!='returned' or row['exit_code']!=1 or row['timed_out']:raise ValueError('both code failures')
        code=(GEN/f'code-{case["seed"]}.private.py').read_bytes()
        log=(EXEC/f'output-{row["index"]}.private.log').read_bytes()
        answer=json.loads((GEN/f'answer-{case["seed"]}.private.json').read_bytes())['answer']
        if sha(code)!=row['code_sha256'] or runtime.SHAPES.search(code+log+answer.encode()):raise ValueError('parent content identity/security')
        case['ancestor']={k:case[k] for k in ('code','term_out','plan','analysis')}
        case.update(code=code.decode(),term_out=log.decode(),prior_answer=answer,
                    prior_code_sha256=sha(code),prior_log_sha256=sha(log),prior_exec_seconds=row['wall_seconds'],
                    request_seed=600+case['seed'],analysis_request_seed=700+case['seed'])
        case['operator']['llm']['generation_kwargs']['seed']=case['request_seed']
        analysis=copy.deepcopy(analyses[case['run']])
        analysis['llm']['client']=copy.deepcopy(case['operator']['llm']['client'])
        old=analysis['llm']['generation_kwargs']
        case['original_analysis_sampling']={k:old.get(k) for k in ('temperature','top_p')}
        analysis['llm']['generation_kwargs']=dict(case['operator']['llm']['generation_kwargs'],
            temperature=old.get('temperature',.6),top_p=old.get('top_p',.95),seed=case['analysis_request_seed'],
            bounded_request_timeout_seconds=300,structured_output_mode='json')
        case['analysis_operator']=analysis
    return cases

async def request(case,preview):
    from omegaconf import OmegaConf
    import numpy as np
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    from dojo.core.solvers.operators.analyze import analyze_op
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.operators.memory import create_memory_op
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    from dojo.core.solvers.utils.response import extract_text_up_to_code
    generic.get_logger=lambda:None
    journal=Journal();root=Node(code='',plan='',analysis='',is_buggy=True,metric=WorstMetricValue());journal.append(root)
    ancestor=Node(code=case['ancestor']['code'],plan=case['ancestor']['plan'],analysis=case['ancestor']['analysis'],
        parents=[root],is_buggy=True,metric=WorstMetricValue(),_term_out=[case['ancestor']['term_out']],exit_code=1,operators_used=['draft'])
    journal.append(ancestor)
    node=Node(code=case['code'],plan=extract_text_up_to_code(case['prior_answer']),parents=[ancestor],
        is_buggy=True,metric=WorstMetricValue(),_term_out=[case['term_out']],exit_code=1,operators_used=['debug'])
    journal.append(node)
    random.seed(case['analysis_request_seed']);np.random.seed(case['analysis_request_seed'])
    started=time.monotonic()
    analysis,ainfo=await first.resolve(analyze_op(generic.GenericLLM(OmegaConf.create(copy.deepcopy(case['analysis_operator']))),
        OmegaConf.create(copy.deepcopy(case['solver'])),case['description'],node))
    analysis_seconds=time.monotonic()-started
    if not isinstance(analysis,dict) or not isinstance(analysis.get('summary'),str):raise ValueError('native analysis schema')
    node.analysis=analysis['summary'];node.operators_used.append('analysis')
    # Actual exit_code=1 is already observed. Never use external grade to decide
    # whether the next repair should happen, even if review hallucinates a metric.
    node.is_buggy=True;node.metric=WorstMetricValue()
    random.seed(case['request_seed']);np.random.seed(case['request_seed'])
    memory=create_memory_op(OmegaConf.create(case['debug_memory']))
    started=time.monotonic()
    answer,info=await first.resolve(debug_op(generic.GenericLLM(OmegaConf.create(copy.deepcopy(case['operator']))),
        OmegaConf.create(copy.deepcopy(case['solver'])),memory,case['description'],journal,node,3,7200,data_preview=preview))
    info['analysis_usage']=ainfo['usage'];info['analysis_seconds']=analysis_seconds
    info['debug_seconds']=time.monotonic()-started
    return answer,info

def cpu(root):
    first.setup(root)
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    from dojo.core.solvers.utils.response import extract_code
    calls=[];cases=runtime.read(root/'inputs.private.json')['cases']
    async def completion(**kwargs):
        case=cases[len(calls)//2];analyze=len(calls)%2==0
        content='\n'.join(str(m.get('content','')) for m in kwargs['messages'])
        assert kwargs['seed']==case['analysis_request_seed' if analyze else 'request_seed']
        assert kwargs['request_timeout'].read==(300 if analyze else 1200)
        assert kwargs['max_retries']==kwargs['num_retries']==0
        assert case['code'].strip() in content
        assert 'liblinear' in content
        if analyze:
            assert kwargs['response_format']=={'type':'json_object'}
            answer=json.dumps(dict(is_bug=True,summary='CPU_NATIVE_ANALYSIS_MARKER',metric=None))
        else:
            assert 'CPU_PUBLIC_PREVIEW' in content
            answer='```python\npass\n```'
        calls.append(dict(seed=kwargs['seed'],analysis=analyze,prompt_sha256=hashlib.sha256(content.encode()).hexdigest()))
        choice=types.SimpleNamespace(message=types.SimpleNamespace(content=answer),finish_reason='stop')
        return types.SimpleNamespace(choices=[choice],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
    async def check():
        with patch.object(backend,'completion_fn',completion):
            for case in cases:
                answer,info=await request(case,'CPU_PUBLIC_PREVIEW')
                assert extract_code(answer).strip()=='pass' and info['analysis_usage']['finish_reason']=='stop'
    asyncio.run(check())
    if len(calls)!=4:raise ValueError('exact four native calls')
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    runtime.write(root/'cpu.json',dict(status='PASS_FOUR_NATIVE_REQUESTS',calls=calls,real_calls=0,prepared_sha256=runtime.sha(root/'prepared.json')))

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    cases=inputs();root=configure(Path(tempfile.mkdtemp(prefix='comparison-depth2-debug-20260919-',dir=BASE)))
    for name in (SCRIPT,PLAN,'run_comparison_live_debug_20260919.py','local_generator_runtime_20260914.py'):
        shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'service_entry.py').write_text(runtime.SERVICE_ENTRY);(root/'service-cache/tmp').mkdir(parents=True)
    runtime.write(root/'inputs.private.json',dict(cases=cases))
    batch=f'''#!/bin/bash
#SBATCH --job-name=comparison-depth2-debug
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=01:20:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 4730s {runtime.PYTHON} -B {root}/{SCRIPT} controller --root {root}
'''
    (root/'run.sbatch').write_text(batch)
    files={str(p.relative_to(root)):runtime.sha(p) for p in root.rglob('*') if p.is_file()}
    runtime.write(root/'prepared.json',dict(commit=commit,utc=runtime.utc(),files=files,parent_summary_sha256=SUMMARY,
        model='cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4',revision='dc430725f831dd90d9271738b877879a46a82239',gpu_hours_cap=4800*2/3600))
    with (root/'.service.env').open('x') as handle:handle.write('PRIMARY_KEY_QWEN3_8_27B='+'0'*64+'\n')
    cpu(root)
    print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',root=str(root),prepared_sha256=runtime.sha(root/'prepared.json'))),flush=True)

def submit(root):
    p=runtime.check_files();runtime.asset_check(p)
    if runtime.read(root/'cpu.json')['prepared_sha256']!=runtime.sha(root/'prepared.json'):raise ValueError('preflight')
    with (root/'capacity.tmp').open('xb') as handle:os.posix_fallocate(handle.fileno(),0,2*1024**3)
    (root/'capacity.tmp').unlink()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).splitlines()
    if set(queue)-{'12535'}:raise ValueError('unexpected concurrent job')
    runtime.write(root/'submit-intent.json',dict(utc=runtime.utc(),gpu_hours_cap=p['gpu_hours_cap']))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
        '--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
    runtime.write(root/'launch.json',dict(job=job,utc=runtime.utc()))
    print(json.dumps(dict(status='SUBMITTED',root=str(root),job=job,gpu_hours_cap=p['gpu_hours_cap'])),flush=True)

def generate(root):
    first.setup(root)
    from dojo.core.solvers.utils import data_preview
    from dojo.core.solvers.utils.response import extract_code
    preview=data_preview.generate(BASE/'mle-bench-data/spooky-author-identification/prepared/public')
    if runtime.SHAPES.search(preview.encode()):raise ValueError('preview security')
    rows=[]
    async def calls():
        for case in runtime.read(root/'inputs.private.json')['cases']:
            started=time.monotonic();row=dict(seed=case['seed'],request_seed=case['request_seed'],analysis_request_seed=case['analysis_request_seed'],source_run=case['run'],status='generation_unknown')
            try:
                answer,info=await asyncio.wait_for(request(case,preview),timeout=1510)
                runtime.write(root/f'answer-{case["seed"]}.private.json',dict(answer=answer,info=info))
                code=extract_code(answer);usage=info['usage'];finish=usage.get('finish_reason')
                row.update(finish_reason=finish,prompt_tokens=usage.get('prompt_tokens'),completion_tokens=usage.get('completion_tokens'),
                    analysis_prompt_tokens=info['analysis_usage'].get('prompt_tokens'),analysis_completion_tokens=info['analysis_usage'].get('completion_tokens'),
                    analysis_seconds=info['analysis_seconds'],debug_seconds=info['debug_seconds'],
                    status='truncated' if finish=='length' else ('code_ready' if code.strip() else 'no_code'))
                if row['status']=='code_ready':
                    if runtime.SHAPES.search(code.encode()) or re.search(r'/prepared/private|/data/private|/research/',code):raise ValueError('generated code scope/security')
                    with (root/f'code-{case["seed"]}.private.py').open('x') as handle:handle.write(code)
                    row['code_sha256']=runtime.sha(root/f'code-{case["seed"]}.private.py')
            except Exception as exc:row.update(status='generation_failed',error_type=type(exc).__name__)
            row['generation_seconds']=time.monotonic()-started
            runtime.write(root/f'generation-{case["seed"]}.json',row);rows.append(row)
    asyncio.run(calls());runtime.write(root/'generation-summary.json',dict(rows=rows,maximum_real_requests=4,paid_api_calls=0,training=False))

if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('role',choices=['prepare','submit','controller','server']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');args=parser.parse_args()
    first.SCRIPT=SCRIPT;first.generate=generate
    if args.role=='prepare':prepare(args.commit)
    else:
        root=configure(args.root)
        if args.role=='server':runtime.server()
        elif args.role=='controller':first.controller(root,service_seconds=4680)
        else:submit(root)
