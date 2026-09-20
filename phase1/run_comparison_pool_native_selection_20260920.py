"""One native analysis per candidate on fixed closed development pools."""
import argparse, asyncio, copy, hashlib, json, math, os, re, shutil, subprocess, sys, tarfile, tempfile, time, types
from pathlib import Path, PurePosixPath
from unittest.mock import patch
import local_generator_runtime_20260914 as rt
import run_comparison_live_debug_20260919 as first

SCRIPT = Path(__file__).name
PLAN = 'comparison_pool_native_selection_plan_20260920.json'
PREFIX = 'comparison-pool-native-selection-20260920-'
QUARANTINE = rt.BASE/'comparison-quarantine-20260919-_tda9fh6'
REWARD = rt.BASE/'comparison-frozen-reward-20260919-ac_f34fz'
REWARD_SHA = 'a1f7f22787e306512f715948d9abc25cbd499d8370880d4f0e286b35c63a68d9'
SOURCES = [
 ('comparison-pool-20260919-7ujiaajp','238bd65e00edd0f678b1f9dc6fbce0c92bf49247030765b64c703ed4d469547a',(1,2)),
 ('comparison-pool-20260919-1z7l72bz','051c550d80b3d9fa50d592f6a615d1ebb02c14a87c6c2dbf0a861b928b52bae4',(3,)),
 ('comparison-spooky-pool-20260919-04qsl2xc','721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1',(1,2))]
IDENTITY = ('task','seed','run','slot','node','code_sha256')

def safe(path, digest=None):
    raw=path.read_bytes()
    if path.is_symlink() or rt.SHAPES.search(raw) or (digest and hashlib.sha256(raw).hexdigest()!=digest):
        raise ValueError('input identity/security')
    return raw

def configure(root):
    if root.resolve(strict=True)!=root or root.parent!=rt.BASE or not re.fullmatch(re.escape(PREFIX)+r'[a-z0-9_]+',root.name):
        raise ValueError('scope')
    rt.ROOT=root; rt.ATTEMPT_SECONDS=3000; first.SCRIPT=SCRIPT
    return root

def setup(root):
    first.setup(root)
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    from comparison_full_deadline_policy_20260919 import install
    install(backend)

def load_cases():
    reward=json.loads(safe(REWARD/'summary.json',REWARD_SHA))
    rank_rows={r['node']:r for r in reward['rows']}
    if len(rank_rows)!=30:raise ValueError('complete frozen population')
    source_rows=[]
    for name,digest,seeds in SOURCES:
        root=rt.BASE/name;summary=json.loads(safe(root/'summary.json',digest))
        for row in summary['rows']:
            if row['seed'] not in seeds:continue
            expected=rank_rows[row['node']]
            if any(row[k]!=expected[k] for k in IDENTITY):raise ValueError('closed identity join')
            if row['status']!='returned' or type(row['exit_code']) is not int or row['timed_out']:raise ValueError('complete untimed execution required')
            # Exact fresh output paths are derived from the closed source row.
            codepath=root/'codes'/f'{row["index"]}.private.py'
            if not codepath.exists():
                # The seed-3 remainder reuses the original immutable code bank.
                codepath=rt.BASE/'comparison-pool-20260919-7ujiaajp/codes'/f'{row["index"]}.private.py'
            code=safe(codepath,row['code_sha256']);log=safe(root/f'output-{row["index"]}.private.log')
            if row.get('log_sha256') and hashlib.sha256(log).hexdigest()!=row['log_sha256']:raise ValueError('fresh log drift')
            source_rows.append({k:row[k] for k in IDENTITY}|dict(code=code.decode(),term_out=log.decode(),
                log_sha256=hashlib.sha256(log).hexdigest(),exit_code=row['exit_code'],timed_out=row['timed_out'],
                source_summary_sha256=digest,source_root=name))
    source_rows.sort(key=lambda r:(r['task'],r['seed'],r['slot']))
    if len(source_rows)!=30 or len({r['node'] for r in source_rows})!=30:raise ValueError('all thirty')
    structure=json.loads(safe(QUARANTINE/'structure.redacted.json','2d87541d73a597b0d487285949b1c8f306e756ae97dc9fde7c175f83783d7d94'))
    wanted={r['run'] for r in source_rows};configs={}
    for task in sorted({r['task'] for r in source_rows}):
        record,=[a for a in structure['archives'] if a['archive']==task+'.tar.gz']
        known={c['path']:c for c in record['configs'] if hashlib.sha256(str(PurePosixPath(c['path']).parent).encode()).hexdigest()[:16] in wanted}
        with tarfile.open(QUARANTINE/'archives'/record['archive'],'r|gz') as archive:
            for member in archive:
                if member.name not in known:continue
                if not member.isfile():raise ValueError('config member')
                raw=archive.extractfile(member).read();expected=known[member.name]
                if hashlib.sha256(raw).hexdigest()!=expected['sha256'] or rt.SHAPES.search(raw):raise ValueError('production config identity/security')
                run=hashlib.sha256(str(PurePosixPath(member.name).parent).encode()).hexdigest()[:16]
                if run in configs:raise ValueError('duplicate config')
                configs[run]=(json.loads(raw)['solver'],expected['sha256'])
    if set(configs)!=wanted:raise ValueError('all exact production configs')
    for i,case in enumerate(source_rows):
        solver,digest=configs[case['run']]
        if solver['use_test_score'] is not False:raise ValueError('external-score-free source')
        operator=copy.deepcopy(solver['operators']['analyze']);old=operator['llm']['generation_kwargs']
        operator['llm']['client']=dict(api='litellm',model_id='qwen3.8-27b',base_url='http://127.0.0.1:8000/v1',provider='selfhosted',use_azure_client=False)
        operator['llm']['generation_kwargs']=dict(bounded_transport=True,bounded_max_attempts=1,bounded_request_timeout_seconds=120,
            # The pinned transport validates this field before the existing
            # full-deadline overlay removes it from actual network kwargs.
            max_tokens=32768,temperature=old.get('temperature',.6),top_p=old.get('top_p',.95),seed=2026092000+i,
            extra_body={'chat_template_kwargs':{'enable_thinking':True}},structured_output_retries=0,structured_output_mode='json')
        description=safe(rt.BASE/'mle-bench-data'/case['task']/'prepared/public/description.md')
        case.update(index=i,request_seed=2026092000+i,operator=operator,config_sha256=digest,description=description.decode(),
            solver={k:solver[k] for k in ('available_packages','execution_timeout','step_limit','data_preview')})
    return source_rows

async def request(case,limit=120):
    from omegaconf import OmegaConf
    import random, numpy as np
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    from dojo.core.solvers.operators.analyze import analyze_op
    from dojo.core.solvers.utils.journal import Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    generic.get_logger=lambda:None;random.seed(case['request_seed']);np.random.seed(case['request_seed'])
    operator=copy.deepcopy(case['operator']);operator['llm']['generation_kwargs']['bounded_request_timeout_seconds']=limit
    node=Node(code=case['code'],plan='',parents=[],_term_out=[case['term_out']],exit_code=case['exit_code'],is_buggy=None,metric=WorstMetricValue())
    response,info=await first.resolve(analyze_op(generic.GenericLLM(OmegaConf.create(operator)),OmegaConf.create(case['solver']),case['description'],node))
    return response,info

def native_decision(case,response):
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.core.solvers.utils.journal import Node
    from dojo.core.tasks.constants import EXECUTION_OUTPUT
    from dojo.core.solvers.utils.metric import WorstMetricValue
    import logging
    node=Node(code='',plan='',parents=[],is_buggy=None,metric=WorstMetricValue())
    result=types.SimpleNamespace(term_out=[case['term_out']],exit_code=case['exit_code'],timed_out=case['timed_out'],exec_time=0.)
    solver=types.SimpleNamespace(cfg=types.SimpleNamespace(use_test_score=False),lower_is_better=True,logger=logging.getLogger('closed-native'),_analyze=lambda _:copy.deepcopy(response))
    MCTS.parse_eval_result(solver,node,{EXECUTION_OUTPUT:result})
    return not node.is_buggy,node.metric.value

def cpu(root):
    setup(root);cases=rt.read(root/'inputs.private.json')['cases'];calls=[]
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    async def completion(**kwargs):
        case=cases[len(calls)];content='\n'.join(str(m.get('content','')) for m in kwargs['messages'])
        assert kwargs['seed']==case['request_seed'] and kwargs['request_timeout'].read==120
        assert 'max_tokens' not in kwargs and kwargs['max_retries']==kwargs['num_retries']==0
        assert kwargs['response_format']=={'type':'json_object'} and case['code'].strip() in content
        assert not set(case)&{'valid','score','independent_score','reward','original_selected','official_grade'}
        calls.append(dict(index=case['index'],request_seed=case['request_seed'],prompt_sha256=hashlib.sha256(content.encode()).hexdigest()))
        response=dict(is_bug=case['exit_code']!=0,summary='CPU_ONLY',metric=.5 if case['exit_code']==0 else None)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=json.dumps(response)),finish_reason='stop')],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
    async def run():
        with patch.object(backend,'completion_fn',completion):
            for case in cases:
                response,_=await request(case);accepted,metric=native_decision(case,response)
                assert accepted==(case['exit_code']==0) and (metric==.5 if accepted else metric is None)
    asyncio.run(run())
    if len(calls)!=30:raise ValueError('matrix')
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    rt.write(root/'cpu.json',dict(status='PASS_THIRTY_REAL_NATIVE_PROMPTS_AND_PARSER_NO_MODEL',calls=calls,real_calls=0,prepared_sha256=rt.sha(root/'prepared.json')))

def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or commit=='0'*40:raise ValueError('real commit')
    cases=load_cases();root=configure(Path(tempfile.mkdtemp(prefix=PREFIX,dir=rt.BASE)))
    files=(SCRIPT,PLAN,'local_generator_runtime_20260914.py','run_comparison_live_debug_20260919.py','comparison_full_deadline_policy_20260919.py',
           'analyze_comparison_native_selection_20260920.py','readout_comparison_native_selection_20260920.py')
    for name in files:shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'service_entry.py').write_text(rt.SERVICE_ENTRY);(root/'service-cache/tmp').mkdir(parents=True)
    rt.write(root/'inputs.private.json',dict(cases=cases))
    batch=f'''#!/bin/bash
#SBATCH --job-name=pool-native-selection
#SBATCH -p gpu_24h
#SBATCH -w gpu28
#SBATCH --gres=gpu:2
#SBATCH -c 12
#SBATCH --time=00:50:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 2940s {rt.PYTHON} -u -B {root}/{SCRIPT} controller --root {root}
'''
    (root/'run.sbatch').write_text(batch)
    files={str(p.relative_to(root)):rt.sha(p) for p in root.rglob('*') if p.is_file()}
    rt.write(root/'prepared.json',dict(commit=commit,utc=rt.utc(),files=files,cases=30,reward_summary_sha256=REWARD_SHA,
        model='cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4',revision='dc430725f831dd90d9271738b877879a46a82239',gpu_hours_cap=3000*2/3600))
    with (root/'.service.env').open('x') as file:file.write('PRIMARY_KEY_QWEN3_8_27B='+'0'*64+'\n')
    print(json.dumps(dict(status='CPU_PREFLIGHT_START',root=str(root),prepared_sha256=rt.sha(root/'prepared.json'))),flush=True)
    cpu(root)
    print(json.dumps(dict(status='PREPARED',root=str(root),prepared_sha256=rt.sha(root/'prepared.json'),cases=30,gpu_hours_cap=3000*2/3600)))

def generate(root):
    setup(root);deadline=time.monotonic()+1800;cases=rt.read(root/'inputs.private.json')['cases']
    async def run():
        for case in cases:
            start=time.monotonic();row={k:case[k] for k in IDENTITY+('index','request_seed','log_sha256','exit_code','timed_out')}
            row.update(status='not_started',native_accepted=None,native_metric=None)
            if deadline-start>1:
                limit=min(120.,deadline-start)
                try:
                    response,info=await asyncio.wait_for(request(case,limit),timeout=limit+1)
                    rt.write(root/f'answer-{case["index"]}.private.json',dict(response=response,info=info))
                    metric=response.get('metric')
                    if type(response.get('is_bug')) is not bool or (metric is not None and (type(metric) not in (int,float) or not math.isfinite(metric))):raise ValueError('analysis schema')
                    if info['usage'].get('finish_reason')!='stop':raise ValueError('incomplete analysis')
                    accepted,native_metric=native_decision(case,response)
                    row.update(status='returned',native_accepted=accepted,native_metric=native_metric,native_is_bug=response['is_bug'],
                        prompt_tokens=info['usage'].get('prompt_tokens'),completion_tokens=info['usage'].get('completion_tokens'))
                except Exception as exc:row.update(status='unknown',error_type=type(exc).__name__)
            row['analysis_seconds']=time.monotonic()-start;rt.write(root/f'analysis-{case["index"]}.json',row)
    asyncio.run(run());rt.write(root/'analysis-complete.json',dict(cases=30,utc=rt.utc(),paid_api_calls=0,training=False))

def submit(root):
    p=rt.check_files();rt.asset_check(p)
    if rt.read(root/'cpu.json')['prepared_sha256']!=rt.sha(root/'prepared.json'):raise ValueError('preflight')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=set(subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split())
    if not jobs<={'12535'}:raise ValueError('unexpected job; no shared service')
    if shutil.disk_usage(root).free<2*1024**3:raise ValueError('output margin')
    rt.write(root/'submit-intent.json',dict(utc=rt.utc(),prepared_sha256=rt.sha(root/'prepared.json'),gpu_hours_cap=p['gpu_hours_cap']))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.private.out'),'--error='+str(root/'allocation-%j.private.err'),str(root/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    rt.write(root/'launch.json',dict(job=job,utc=rt.utc()));print(json.dumps(dict(status='SUBMITTED',job=job,root=str(root))))

if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','controller','server']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');args=parser.parse_args()
    if args.mode=='prepare':prepare(args.commit)
    else:
        configure(args.root)
        if args.mode=='submit':submit(args.root)
        elif args.mode=='server':rt.server()
        else:first.generate=generate;first.controller(args.root,service_seconds=2880,closed_status='all_thirty_analyses_closed')
