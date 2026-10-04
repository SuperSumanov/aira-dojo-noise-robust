"""Bounded posthoc role crossover on ALL 22 closed development observations.

Only delivered model identity changes within a prompt/seed pair. No program
execution, training, hidden scoring, result rescue, or semantic-validity claim.
"""
import argparse,asyncio,copy,datetime,hashlib,importlib.util,json,logging,os,re,secrets,shutil,signal,socket,subprocess,sys,time
from pathlib import Path
OLD=Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')
R=Path('/research/d7/spc/yzyang4/policy9b-role-cross-20261005-v1')
PY=Path('/research/d7/spc/yzyang4/venvs/aira/bin/python')
SEEDS=(109501,109511)
MODELS={'base':'qwen3.5-9b','sft':'qwen3.5-9b-mle-lora'}
SECRET=re.compile(rb'(?i)(?:\bsk-[a-z0-9_.-]{12,}|\bhf_[a-z0-9]{20,}|\bgh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,x):
    raw=json.dumps(x,indent=2,sort_keys=True,allow_nan=False).encode()
    assert not SECRET.search(raw),'credential-shaped artifact'
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def native():
    p=OLD/'policy9b_paired_20261005.py'
    assert sha(p)=='b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
    s=importlib.util.spec_from_file_location('fixed_native_role_host',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    m.R=R;m.check=lambda:check();return m
def setup():
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',LITELLM_LOCAL_MODEL_COST_MAP='True',
        LOGGING_DIR=str(R),SUPERIMAGE_DIR=str(R/'no-image'),MLE_BENCH_DATA_DIR=str(R/'no-data'),
        HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',NO_PROXY='127.0.0.1,localhost',no_proxy='127.0.0.1,localhost')
    sys.path.insert(0,str(OLD/'source/src'));sys.path.insert(0,str(R));logging.disable(logging.CRITICAL)
def check():
    plan=read(R/'plan.json')
    for p,h in plan['files'].items():assert sha(R/p)==h,p
    assert sha(OLD/'readout-v1/summary.json')==plan['source_summary_sha256']
    for p,h in plan['source_files'].items():assert sha(OLD/p)==h,p
    return plan
def prepare():
    assert not R.exists();assert read(OLD/'readout-v1/summary.json')['status']=='CLOSED_DEVELOPMENT_QUALIFICATION'
    R.mkdir(mode=0o700)
    for d in ('service-cache/tmp','records','attempts'):(R/d).mkdir(parents=True,exist_ok=True)
    source_files={}
    frozen=read(OLD/'plan.json')
    for name,h in frozen['files'].items():
        if name.startswith('source/') or name=='configs/0.json':
            assert sha(OLD/name)==h
            source_files[name]=h
    # Shared immutable inference helpers and exact source; no old task workspaces.
    for name in ('forets_native_cuda_identity_20260911.py','forets_native_gpu_binding_20260911.py','service_entry.py'):
        assert sha(OLD/name)==frozen['files'][name]
        shutil.copyfile(OLD/name,R/name);source_files[name]=sha(OLD/name)
    shutil.copyfile(__file__,R/Path(__file__).name)
    with (R/'.service.env').open('x') as f:f.write('PRIMARY_KEY_QWEN3_8_27B='+secrets.token_hex(32)+'\n')
    os.chmod(R/'.service.env',0o600)
    cases=[]
    for s in frozen['schedule']:
        jp=OLD/f"episode-{s['index']}/checkpoint/journal.jsonl";raw=jp.read_bytes();assert not SECRET.search(raw)
        source_files[str(jp.relative_to(OLD))]=sha(jp)
        candidates={read(p)['code_sha256']:read(p) for p in jp.parent.parent.glob('candidate-*.json') if not p.name.endswith('.private.json')}
        for node in (json.loads(x) for x in raw.splitlines() if x):
            if not node.get('operators_used'):continue
            c=candidates[hashlib.sha256(node['code'].encode()).hexdigest()]
            metrics=[m for role,m in zip(node['operators_used'],node['operators_metrics']) if role=='analysis'];assert len(metrics)==1
            messages=metrics[0]['prompt_messages'];assert len(messages)==2
            assert all(m['role'] in ('system','user') and isinstance(m['content'],str) for m in messages)
            cases.append(dict(case=len(cases),source_run=s['index'],source_arm=s['arm'],task=s['task'],
                code_sha256=c['code_sha256'],objective_valid=bool(c['valid'] and c['exit_code']==0 and not c['timed_out']),
                prompt_sha256=hashlib.sha256(json.dumps(messages,sort_keys=True).encode()).hexdigest(),messages=messages))
    assert len(cases)==22 and sum(c['objective_valid'] for c in cases)==3
    write(R/'cases.private.json',cases)
    calls=[]
    for repeat,seed in enumerate(SEEDS):
        for c in cases:
            for arm in (('base','sft') if (c['case']+repeat)%2==0 else ('sft','base')):
                calls.append(dict(index=len(calls),case=c['case'],source_run=c['source_run'],task=c['task'],arm=arm,seed=seed))
    assert len(calls)==88
    batch=f'''#!/bin/bash
#SBATCH --job-name=policy9b-role-cross
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=00:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=25s 2340s {PY} -B {R}/policy9b_role_cross_20261005.py controller
'''
    (R/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and p.name!='.service.env'}
    write(R/'plan.json',dict(protocol='posthoc-shared-analysis-input-model-crossover-v1',utc=utc(),files=files,source_files=source_files,
        source_summary_sha256=sha(OLD/'readout-v1/summary.json'),calls=calls,allocation_gpus=2,allocation_seconds=2400,
        gpu_hours_cap=2*2400/3600,window_previous_gpu_hours=read(OLD/'readout-v1/summary.json')['allocated_gpu_hours'],
        question='Does delivered LoRA change analysis decisions on identical already-executed observations?',
        cases=22,objective_valid=3,source_runs=8,seeds=list(SEEDS),all_cases_included=True,
        primary='Per repeat/model counts: parsed, false veto among 3 objective-valid cases, false accept among 19 objective-invalid, missing; per case/run paired tables. No overall accuracy headline on imbalanced case mix.',
        qualification='Descriptive only: fewer valid-case vetoes in BOTH repeats without more invalid-case acceptance or missing answers. No E2E continuation is authorized by this diagnostic.',
        limitations='Posthoc fixed observations, only three valid cases in two source runs, all valid from Spooky. Objective validity is not semantic correctness/anti-cheating. Repeats are not independent tasks. No held-out generalization or model-search-gain claim.',
        changes='Only model identity within identical prompt/seed pair. Same original analysis params/schema/client, BF16/TP2/context32768/nonthinking; order counterbalanced.',
        actual_program_execution=0,own_training=0,paid_api=0,protected_data_opened=False))
    cpu();print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),cases=22,calls=88,gpu_hours_cap=2*2400/3600)))
def config(arm,seed):
    setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.core.solvers.llm_helpers.backends.utils import get_client
    cfg=RunConfig.load_from_json(OLD/'configs/0.json').solver.operators['analyze'].llm
    cfg.client.model_id=MODELS[arm];cfg.generation_kwargs['seed']=seed
    return get_client(cfg.client),copy.deepcopy(cfg.generation_kwargs)
def cpu():
    plan=check();setup()
    os.environ.update(PRIMARY_KEY='fixture',PRIMARY_KEY_QWEN3_5_9B='fixture',PRIMARY_KEY_QWEN3_5_9B_MLE_LORA='fixture')
    for seed in SEEDS:
        a,kw=config('base',seed);b,other=config('sft',seed);assert kw==other
        assert kw['seed']==seed and kw['extra_body']['chat_template_kwargs']['enable_thinking'] is False
        json.dumps(kw)
    # Native bounded client + JSON schema via mocked completion, never network.
    from unittest.mock import patch
    from dojo.core.solvers.operators.analyze import analyze_schema_with_eval
    import litellm
    import dojo.core.solvers.llm_helpers.backends.lite_llm as backend
    captured=[]
    async def fake(**kw):
        captured.append(kw)
        return litellm.ModelResponse(model=kw['model'],choices=[{'index':0,'message':{'role':'assistant','content':'{"is_bug":false,"summary":"fixture","metric":0.5}'},'finish_reason':'stop'}],usage={'prompt_tokens':5,'completion_tokens':3,'total_tokens':8})
    async def probe():
        for arm in MODELS:
            client,kw=config(arm,SEEDS[0])
            answer,usage=await client.query([dict(role='user',content='fixture')],json_schema=analyze_schema_with_eval,
                function_name='submit_review',function_description='Submit a review evaluating the output of the training script.',**kw)
            assert answer['is_bug'] is False
    with patch.object(backend,'completion_fn',fake),patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
        asyncio.run(probe())
    assert len(captured)==2
    assert captured[0]['model']!=captured[1]['model']
    write(R/'cpu.json',dict(status='PASS',plan_sha256=sha(R/'plan.json'),queries_mocked=2,pairs_same_params=2,external_requests=0,model_calls=0))
def submit():
    plan=check();assert read(R/'cpu.json')['plan_sha256']==sha(R/'plan.json')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split();assert not set(jobs)-{'12535'}
    write(R/'submit-intent.json',dict(utc=utc(),plan_sha256=sha(R/'plan.json')))
    run=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=run.stdout.strip().split(';')[0];assert run.returncode==0 and job.isdigit(),'ambiguous submit; never retry'
    write(R/'launch.json',dict(job=job,utc=utc(),plan_sha256=sha(R/'plan.json')));print(json.dumps(dict(status='SUBMITTED',job=job)))
def service():setup();native().service()
def controller():
    plan=check();setup();assert socket.gethostname().split('.')[0]=='gpu27'
    m=native();start=time.monotonic();write(R/'claim.json',dict(utc=utc(),job=os.environ['SLURM_JOB_ID']))
    env=m.infra().clean_env();cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=12','--gres=gpu:2','--time=00:39:00',str(PY),'-B',str(R/Path(__file__).name),'service']
    with (R/'service.private.log').open('xb') as log:
        server=subprocess.Popen(cmd,env=env,stdout=log,stderr=log,start_new_session=True)
        try:
            while time.monotonic()-start<900:
                if server.poll() is not None:raise RuntimeError('service exited')
                try:
                    if m.health():break
                except Exception:pass
                time.sleep(3)
            else:raise TimeoutError('service readiness')
            key=m.infra().local_key();os.environ.update(PRIMARY_KEY=key,PRIMARY_KEY_QWEN3_5_9B=key,PRIMARY_KEY_QWEN3_5_9B_MLE_LORA=key)
            write(R/'ready.json',dict(utc=utc(),startup_seconds=time.monotonic()-start,models=sorted(MODELS.values())))
            cases=read(R/'cases.private.json')
            from dojo.core.solvers.operators.analyze import analyze_schema_with_eval
            for call in plan['calls']:
                if time.monotonic()-start>2110:break
                assert server.poll() is None
                write(R/'attempts'/f"{call['index']}.json",dict(**call,utc=utc()))
                client,kw=config(call['arm'],call['seed']);case=cases[call['case']];t=time.monotonic()
                record=dict(**call,prompt_sha256=case['prompt_sha256'],requested_model=MODELS[call['arm']],status='failed')
                try:
                    answer,usage=asyncio.run(client.query(copy.deepcopy(case['messages']),json_schema=analyze_schema_with_eval,
                        function_name='submit_review',function_description='Submit a review evaluating the output of the training script.',**kw))
                    write(R/'records'/f"{call['index']}.private.json",dict(answer=answer,usage=usage))
                    parsed=isinstance(answer,dict) and type(answer.get('is_bug')) is bool
                    record.update(status='parsed' if parsed else 'unparsed',is_bug=answer.get('is_bug') if parsed else None,
                        prompt_tokens=usage.get('prompt_tokens'),completion_tokens=usage.get('completion_tokens'))
                except Exception as exc:record['error_type']=type(exc).__name__
                record['elapsed_seconds']=time.monotonic()-t
                write(R/'records'/f"{call['index']}.json",record)
            write(R/'queries-closed.json',dict(utc=utc(),completed=sum(not p.name.endswith('.private.json') for p in (R/'records').glob('[0-9]*.json'))))
        except Exception as exc:write(R/'failure.json',dict(utc=utc(),error_type=type(exc).__name__));raise
        finally:
            if server.poll() is None:
                server.send_signal(signal.SIGTERM)
                try:server.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    step=read(R/'service-native.json')['step'];assert step.isdigit()
                    subprocess.run(['scancel','--signal=KILL',os.environ['SLURM_JOB_ID']+'.'+step],env=env,check=True,timeout=25);server.wait(timeout=20)
            write(R/'closed.json',dict(utc=utc(),elapsed_seconds=time.monotonic()-start,service_closed=server.poll() is not None))
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','cpu','submit','service','controller','check']);a=p.parse_args()
    if a.mode=='check':check();print('FROZEN_CHECK_PASS')
    else:globals()[a.mode]()
