"""Fresh native debug draws on fixed admitted development prefixes, no model fit."""
import argparse,asyncio,copy,hashlib,inspect,json,logging,os,random,re,secrets,shutil,socket,subprocess,sys,tarfile,tempfile,time,types
from pathlib import Path,PurePosixPath
from unittest.mock import patch
import local_generator_runtime_20260914 as runtime

BASE=runtime.BASE
OLD=BASE/'comparison-spooky-pool-20260919-04qsl2xc'
ARCHIVE=BASE/'comparison-quarantine-20260919-_tda9fh6/archives/spooky-author-identification.tar.gz'
RUNS={1:'3277c81be72a1c30',2:'58d3914785a2cfe1'}
# Canonical node identity is selected by step=1 in the admitted nodes export,
# then checked against the closed execution receipt.
CONFIG_SHAS={'3277c81be72a1c30':'630361b87c9f153765c1b623c5b27209ffd931c3383d0183fa0c0c68968e7293',
             '58d3914785a2cfe1':'3e4454a0a749464995e223725587d1c5d428d689d25f26628f2714aab7a886b7'}
SCRIPT=Path(__file__).name
PLAN='comparison_live_debug_plan_20260919.json'


def configure(root):
    root=root.resolve(strict=True)
    if root.parent!=BASE or not re.fullmatch(r'comparison-live-debug-20260919-[a-z0-9_]+',root.name):raise ValueError('root scope')
    runtime.ROOT=root;runtime.ATTEMPT_SECONDS=5400
    return root


def prefix_inputs():
    from run_comparison_reuse_20260919 import PREFIX_ERRORS,read,sha
    nodes=read(BASE/'comparison-quarantine-20260919-_tda9fh6/qwen-readout-v1/nodes.json',
               '370976e31c8a9f501bc75fb7826f529f85b0e34059146291f2e7bb3cab4062c9')
    summary=read(OLD/'summary.json','721f995ca597568303f65c32e9d04667bcdd173c174b2e6af99bb78e765c0eb1')
    prepared=read(OLD/'prepared.json','e3337e7affc534e6e0c3e4e2a75571fc08a9b4a7c271877a71073dda5e8917d6')
    cases=[];configs={};original_nodes={}
    for seed,run in RUNS.items():
        n,=[n for n in nodes if n['run']==run and n['group']=='executed' and n['step']==1]
        if n['parents']!=[0] or 'draft' not in n['operators_used']:raise ValueError('prefix structure')
        row,=[r for r in prepared['rows'] if r['node']==n['id'] and r['run']==run]
        if row['raw_code_sha256']!=n['code_sha256']:raise ValueError('source code mismatch')
        outcome,=[r for r in summary['rows'] if r['index']==row['index']]
        if outcome['valid'] is not False or outcome['exit_code']!=1 or outcome['timed_out']:raise ValueError('closed prefix error')
        raw=(OLD/'codes'/f'{row["index"]}.raw.private.py').read_bytes()
        log=(OLD/f'output-{row["index"]}.private.log').read_bytes()
        if sha(raw)!=n['code_sha256'] or runtime.SHAPES.search(raw+log):raise ValueError('prefix identity/security')
        terminal=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',log.decode())
        if not terminal.rstrip().endswith(PREFIX_ERRORS[seed]):raise ValueError('prefix terminal error')
        cases.append(dict(seed=seed,request_seed=500+seed,run=run,node=n['id'],code=raw.decode(),
                          term_out=log.decode(),raw_code_sha256=sha(raw),log_sha256=sha(log)))
    wanted={c['node'] for c in cases}
    with tarfile.open(ARCHIVE,'r|gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if not member.isfile():continue
            if path.name=='dojo_config.json':
                run=hashlib.sha256(str(path.parent).encode()).hexdigest()[:16]
                if run not in CONFIG_SHAS:continue
                raw=archive.extractfile(member).read()
                if sha(raw)!=CONFIG_SHAS[run] or runtime.SHAPES.search(raw):raise ValueError('original config identity/security')
                configs[run]=json.loads(raw)
            elif path.name=='journal.jsonl':
                run=hashlib.sha256(str(path.parent.parent).encode()).hexdigest()[:16]
                if run not in CONFIG_SHAS:continue
                for line in archive.extractfile(member):
                    if runtime.SHAPES.search(line):raise ValueError('credential shape in prefix journal')
                    n=json.loads(line)
                    if n.get('id') in wanted:
                        if n['id'] in original_nodes:raise ValueError('duplicate prefix')
                        original_nodes[n['id']]=n
    if set(configs)!=set(CONFIG_SHAS) or set(original_nodes)!=wanted:raise ValueError('complete source inputs')
    description=(BASE/'mle-bench-data/spooky-author-identification/prepared/public/description.md').read_bytes()
    if runtime.SHAPES.search(description):raise ValueError('description security')
    for case in cases:
        solver=configs[case['run']]['solver'];old=original_nodes[case['node']]
        if solver['use_test_score'] is not False:raise ValueError('private score input disabled')
        operator=copy.deepcopy(solver['operators']['debug']);g=operator['llm']['generation_kwargs']
        if g.get('temperature')!=.6 or g.get('top_p')!=.95:raise ValueError('original sampling changed')
        operator['llm']['client']=dict(api='litellm',model_id='qwen3.8-27b',base_url='http://127.0.0.1:8000/v1',provider='selfhosted',use_azure_client=False)
        operator['llm']['generation_kwargs']=dict(bounded_transport=True,bounded_max_attempts=1,
            bounded_request_timeout_seconds=1200,max_tokens=32768,temperature=.6,top_p=.95,seed=case['request_seed'],
            extra_body={'chat_template_kwargs':{'enable_thinking':True}},structured_output_retries=0)
        case.update(operator=operator,solver={k:solver[k] for k in ('available_packages','execution_timeout','step_limit','data_preview')},
                    debug_memory=solver['debug_memory'],description=description.decode(),plan=old.get('plan'),analysis=old.get('analysis'),
                    description_sha256=sha(description),config_sha256=CONFIG_SHAS[case['run']])
    return cases


def setup(root):
    p=runtime.check_files();runtime.setup_worker(p)
    return p


def request(case,preview):
    from omegaconf import OmegaConf
    import numpy as np
    import dojo.core.solvers.llm_helpers.generic_llm as generic
    from dojo.core.solvers.operators.debug import debug_op
    from dojo.core.solvers.operators.memory import create_memory_op
    from dojo.core.solvers.utils.journal import Journal,Node
    from dojo.core.solvers.utils.metric import WorstMetricValue
    random.seed(case['request_seed']);np.random.seed(case['request_seed'])
    generic.get_logger=lambda:None
    journal=Journal();parent=Node(code='',plan='',analysis='',is_buggy=True,metric=WorstMetricValue())
    journal.append(parent)
    node=Node(code=case['code'],plan=case['plan'],analysis=case['analysis'],parents=[parent],
              is_buggy=True,metric=WorstMetricValue(),_term_out=[case['term_out']],exit_code=1,operators_used=['draft'])
    journal.append(node)
    memory=create_memory_op(OmegaConf.create(case['debug_memory']))
    return debug_op(generic.GenericLLM(OmegaConf.create(case['operator'])),OmegaConf.create(copy.deepcopy(case['solver'])),
                    memory,case['description'],journal,node,2,7200,data_preview=preview)


async def resolve(value):
    return await value if inspect.isawaitable(value) else value


def cpu(root):
    setup(root)
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    from dojo.core.solvers.utils.response import extract_code
    calls=[];cases=runtime.read(root/'inputs.private.json')['cases']
    async def complete(**kwargs):
        case=cases[len(calls)]
        messages=kwargs['messages'];text=json.dumps(messages)
        content='\n'.join(str(m.get('content','')) for m in messages)
        import humanize
        checks=dict(route=kwargs['model']=='openai/qwen3.8-27b' and kwargs['base_url']=='http://127.0.0.1:8000/v1',
                    seed=kwargs['seed']==case['request_seed'],tokens=kwargs['max_tokens']==32768,
                    timeout=kwargs['request_timeout'].read==1200,retries=kwargs['max_retries']==kwargs['num_retries']==0,
                    code=case['code'].strip() in content,preview='CPU_PUBLIC_PREVIEW' in content,
                    budget=humanize.naturaldelta(7200) in content)
        print(json.dumps(dict(event='CPU_REQUEST_CHECKS',seed=case['request_seed'],checks=checks)),flush=True)
        assert all(checks.values())
        calls.append(dict(seed=case['request_seed'],prompt_sha256=hashlib.sha256(text.encode()).hexdigest()))
        choice=types.SimpleNamespace(message=types.SimpleNamespace(content='```python\npass\n```'),finish_reason='stop')
        return types.SimpleNamespace(choices=[choice],to_dict=lambda:{'usage':{'prompt_tokens':1,'completion_tokens':1}})
    async def test():
        with patch.object(backend,'completion_fn',complete):
            for case in cases:
                answer,info=await resolve(request(case,'CPU_PUBLIC_PREVIEW'))
                assert extract_code(answer).strip()=='pass' and info['usage']['finish_reason']=='stop'
    asyncio.run(test())
    if len(calls)!=2:raise ValueError('both debug calls')
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True,timeout=10)
    runtime.write(root/'cpu.json',dict(status='PASS_TWO_NATIVE_DEBUG_MOCK_REQUESTS',calls=calls,prepared_sha256=runtime.sha(root/'prepared.json'),real_model_calls=0))
    print(json.dumps(dict(status='PASS_TWO_NATIVE_DEBUG_MOCK_REQUESTS',calls=2)))


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('commit')
    cases=prefix_inputs();root=Path(tempfile.mkdtemp(prefix='comparison-live-debug-20260919-',dir=BASE));configure(root)
    for name in (SCRIPT,'local_generator_runtime_20260914.py',PLAN):shutil.copy2(Path(__file__).with_name(name),root/name)
    (root/'service_entry.py').write_text(runtime.SERVICE_ENTRY)
    (root/'service-cache/tmp').mkdir(parents=True)
    runtime.write(root/'inputs.private.json',dict(cases=cases))
    batch='''#!/bin/bash
#SBATCH --job-name=comparison-live-debug
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 5330s __PYTHON__ -B ROOT/SCRIPT controller --root ROOT
'''.replace('__PYTHON__',str(runtime.PYTHON)).replace('ROOT',str(root)).replace('SCRIPT',SCRIPT)
    (root/'run.sbatch').write_text(batch)
    files={str(p.relative_to(root)):runtime.sha(p) for p in root.rglob('*') if p.is_file()}
    runtime.write(root/'prepared.json',dict(commit=commit,utc=runtime.utc(),files=files,
        model='cyankiwi/Qwen3.8-27B-AWQ-BF16-INT4',revision='dc430725f831dd90d9271738b877879a46a82239',gpu_hours_cap=3))
    # Synthetic local auth only for CPU preflight; controller replaces it by a
    # unique random credential before any server starts, never using user keys.
    with (root/'.service.env').open('x') as handle:handle.write('PRIMARY_KEY_QWEN3_8_27B='+'0'*64+'\n')
    cpu(root)
    print(json.dumps(dict(root=str(root),status='PREPARED_NOT_SUBMITTED',prepared_sha256=runtime.sha(root/'prepared.json'))))


def submit(root):
    p=runtime.check_files();runtime.asset_check(p)
    if runtime.read(root/'cpu.json')['prepared_sha256']!=runtime.sha(root/'prepared.json'):raise ValueError('preflight drift')
    with (root/'capacity.tmp').open('xb') as handle:os.posix_fallocate(handle.fileno(),0,2*1024**3)
    (root/'capacity.tmp').unlink()
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    lines=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i|%T'],env=env,text=True,timeout=20).splitlines()
    if any(line.split('|')[0] not in ('12535','14115') for line in lines) or len(lines)>2:raise ValueError('unexpected concurrent allocation')
    runtime.write(root/'submit-intent.json',dict(utc=runtime.utc(),prepared_sha256=runtime.sha(root/'prepared.json'),gpu_hours_cap=3))
    p=subprocess.run(['sbatch','--parsable','--chdir='+str(root),'--output='+str(root/'allocation-%j.out'),
                      '--error='+str(root/'allocation-%j.err'),str(root/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=p.stdout.strip().split(';')[0]
    if p.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
    runtime.write(root/'launch.json',dict(job=job,utc=runtime.utc(),gpu_hours_cap=3))
    print(json.dumps(dict(status='SUBMITTED',job=job,root=str(root),gpu_hours_cap=3)))


def generate(root):
    setup(root)
    from dojo.core.solvers.utils import data_preview
    from dojo.core.solvers.utils.response import extract_code
    preview=data_preview.generate(BASE/'mle-bench-data/spooky-author-identification/prepared/public')
    if runtime.SHAPES.search(preview.encode()):raise ValueError('preview security')
    rows=[]
    async def calls():
        for case in runtime.read(root/'inputs.private.json')['cases']:
            started=time.monotonic();row=dict(seed=case['seed'],request_seed=case['request_seed'],source_run=case['run'],status='generation_unknown')
            try:
                answer,info=await asyncio.wait_for(resolve(request(case,preview)),timeout=1210)
                runtime.write(root/f'answer-{case["seed"]}.private.json',dict(answer=answer,info=info))
                code=extract_code(answer);usage=info['usage'];finish=usage.get('finish_reason')
                row.update(finish_reason=finish,prompt_tokens=usage.get('prompt_tokens'),completion_tokens=usage.get('completion_tokens'),
                           status='truncated' if finish=='length' else ('code_ready' if code.strip() else 'no_code'))
                if row['status']=='code_ready':
                    if runtime.SHAPES.search(code.encode()) or re.search(r'/prepared/private|/data/private|/research/',code):raise ValueError('generated code scope/security')
                    with (root/f'code-{case["seed"]}.private.py').open('x') as handle:handle.write(code)
                    row['code_sha256']=runtime.sha(root/f'code-{case["seed"]}.private.py')
            except Exception as exc:row.update(status='generation_failed',error_type=type(exc).__name__)
            row['generation_seconds']=time.monotonic()-started
            runtime.write(root/f'generation-{case["seed"]}.json',row);rows.append(row)
    asyncio.run(calls());runtime.write(root/'generation-summary.json',dict(rows=rows,live_requests=2,paid_api_calls=0,training=False))


def controller(root):
    p=runtime.check_files();runtime.asset_check(p)
    if socket.gethostname().split('.')[0]!='gpu28' or runtime.read(root/'launch.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('allocation identity')
    with socket.socket() as sock:sock.bind(('127.0.0.1',8000))
    runtime.write(root/'execution.claim.json',dict(job=os.environ['SLURM_JOB_ID'],utc=runtime.utc()))
    # Only this root's synthetic preflight auth is replaced, before a server exists.
    with (root/'.service.env').open('w') as handle:handle.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    env=dict(os.environ)
    for k in ('CUDA_VISIBLE_DEVICES','SLURM_STEP_GPUS','SLURM_STEP_ID','GPU_DEVICE_ORDINAL','PRIMARY_KEY','OPENROUTER_API_KEY'):env.pop(k,None)
    cmd=['srun','--jobid='+os.environ['SLURM_JOB_ID'],'--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6',
         '--gres=gpu:2','--time=01:28:00',str(runtime.PYTHON),'-B',str(root/SCRIPT),'server','--root',str(root)]
    start=time.monotonic();status='startup_failed'
    with (root/'service.private.log').open('xb') as log:
        process=subprocess.Popen(cmd,env=env,stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
        try:
            while time.monotonic()-start<1500:
                if process.poll() is not None:raise RuntimeError('service exited')
                try:healthy=runtime.own_health()
                except Exception:healthy=False
                if healthy:break
                time.sleep(2)
            else:raise RuntimeError('service startup deadline')
            runtime.write(root/'ready.json',dict(startup_seconds=time.monotonic()-start,utc=runtime.utc()))
            generate(root);status='two_draws_closed'
        finally:
            runtime.stop_owned(process)
            runtime.write(root/'closed.json',dict(status=status,utc=runtime.utc(),controller_seconds=time.monotonic()-start,job=os.environ['SLURM_JOB_ID']))


if __name__=='__main__':
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('role',choices=['prepare','submit','controller','server']);parser.add_argument('--root',type=Path);parser.add_argument('--commit');args=parser.parse_args()
    if args.role=='prepare':prepare(args.commit)
    else:
        root=configure(args.root)
        if args.role=='server':runtime.server()
        else:globals()[args.role](root)
