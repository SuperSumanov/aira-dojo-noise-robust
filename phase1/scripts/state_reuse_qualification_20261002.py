"""Real public-data computation reuse qualification; no evaluator or generator.

Two existing programs x two initialization seeds. Each builds a paid initial
state, queries its public OOF evidence, then repeats the identical computation
in a new interpreter. Exact output identity is a gate, not assumed correctness.
"""
import argparse, copy, hashlib, importlib.util, json, os, re, shutil
import subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

B = Path('/research/d7/spc/yzyang4')
OLD = B/'decision-diagnosis-20261002-v1'
ROOT = B/'state-reuse-qualification-20261002-v1'
PY = B/'venvs/aira/bin/python'
COMMIT = 'f0d18a56ea8ebd2dbb2836d4037602e022fca7a8'
SEEDS = (103101, 103102)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def read(p): return json.loads(Path(p).read_text())
def write(p, x):
    with Path(p).open('x') as f: json.dump(x, f, indent=2)
def runtime():
    p = ROOT/'v6_runtime.py'
    if sha(p) != '4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad':
        raise ValueError('runtime drift')
    s=importlib.util.spec_from_file_location('state_reuse_base',p)
    m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
    m.ROOT=ROOT;m.infra.ROOT=ROOT;m.setup()
    return m

def diagnostic(i):
    # Public, previously generated OOF predictions only. No D_search scorer.
    if i == 0:
        body='''
arrays = {k: np.asarray(models[k][0]) for k in sorted(models)}
target = np.asarray(y)
lengths = train['request_text_edit_aware'].fillna('').astype(str).str.len().to_numpy()
metric = lambda yy, pp: float(roc_auc_score(yy, pp))
'''
    else:
        body='''
arrays = {'tfidf': np.asarray(oof_tfidf_c), 'embedding': np.asarray(oof_emb_c)}
target = np.asarray(y_train)
lengths = train_df['text'].fillna('').astype(str).str.len().to_numpy()
metric = lambda yy, pp: float(log_loss(yy, pp, labels=[0,1,2]))
'''
    return '''
import hashlib as _hashlib, json as _json
from pathlib import Path as _Path
''' + body + '''
cuts = np.quantile(lengths, [1/3, 2/3])
groups = np.searchsorted(cuts, lengths, side='right')
result = {'arrays':{}, 'group_metrics':{}, 'n':len(target)}
for key, arr in arrays.items():
    result['arrays'][key] = _hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()
    result['group_metrics'][key] = [metric(target[groups==g], arr[groups==g]) for g in range(3)]
result['submission_sha256'] = _hashlib.sha256(_Path('submission.csv').read_bytes()).hexdigest()
print('REUSE_RECEIPT '+_json.dumps(result, sort_keys=True))
'''

def check():
    p=read(ROOT/'plan.json')
    for f,h in p['files'].items():
        if sha(ROOT/f)!=h: raise ValueError('frozen file drift '+f)
    return p

def prepare():
    if ROOT.exists(): raise FileExistsError(ROOT)
    if sha(OLD/'plan.json')!='939f9470529ad6c14f5b6670bb1bec4cd99398026f6fbdbea662c8d29e32c48e':
        raise ValueError('source plan drift')
    ROOT.mkdir(mode=0o700)
    p=read(OLD/'plan.json')
    for rel,h in p['files'].items():
        if not rel.startswith(('source/','forets_','opencl-vendors/')): continue
        if sha(OLD/rel)!=h: raise ValueError('source file drift')
        dst=ROOT/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(OLD/rel,dst)
    shutil.copyfile(OLD/'v6_runtime.py',ROOT/'v6_runtime.py')
    shutil.copyfile(__file__,ROOT/'state_reuse_qualification_20261002.py')
    (ROOT/'bin').mkdir();(ROOT/'configs').mkdir();(ROOT/'starts').mkdir()
    wrapper=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom state_reuse_qualification_20261002 import runtime\nruntime().task_runtime()\n'
    (ROOT/'bin/singularity').write_text(wrapper);os.chmod(ROOT/'bin/singularity',0o700)
    for i in range(2):
        raw=(OLD/'starts'/f'{i}.private.json').read_bytes()
        if re.search(rb'(?i)sk-[a-z0-9_.-]{12,}',raw): raise ValueError('credential shape')
        (ROOT/'starts'/f'{i}.private.json').write_bytes(raw)
        cfg=read(OLD/'configs'/f'{i}.json')
        cfg['logger'].update(output_dir=str(ROOT/f'episode-{i}/native-log'),write_env_vars=False,
                             print_config=False,use_console=False,use_wandb=False)
        # No task object is instantiated and no evaluator function is imported.
        write(ROOT/'configs'/f'{i}.json',cfg);(ROOT/f'episode-{i}').mkdir()
    batch=f'''#!/bin/bash
#SBATCH --job-name=state-reuse-cost
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=12
#SBATCH --time=00:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 1740s {PY} -B {ROOT}/state_reuse_qualification_20261002.py controller
'''
    (ROOT/'run.sbatch').write_text(batch)
    files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file()}
    write(ROOT/'plan.json',dict(protocol='state-reuse-public-cost-v1',commit=COMMIT,files=files,
        seeds=SEEDS,tasks=2,initial_builds=4,cold_replays=4,retained_queries=4,
        task_seconds=1600,execution_cap=300,gpu_hours_cap=1,paid_api=0,generator_calls=0,
        endpoint='exact public diagnostic and submission hashes, complete elapsed cost',
        gate='all 4 exact-equal public payloads; each task median cold/warm wall ratio >2',
        qualification_only=True,hidden_score_reads=False,
        limitations='historical selected programs; public OOF is not unbiased test accuracy; fixed cold-after-warm order'))
    cpu()

def cpu():
    import ast
    p=check();m=runtime()
    from dojo.config_dataclasses.run import RunConfig
    for i in range(2):
        cfg=RunConfig.load_from_json(ROOT/'configs'/f'{i}.json');cfg.validate()
        code=read(ROOT/'starts'/f'{i}.private.json')['code']
        ast.parse(code);ast.parse(diagnostic(i))
        if Path(cfg.task.private_dir).exists(): raise ValueError('private task bind exists')
        if cfg.interpreter.env.get('OMP_NUM_THREADS')!='6': raise ValueError('thread budget')
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    # Safety assertions cover the actual source, not just a separate mock path.
    tree=ast.parse(Path(__file__).read_text())
    calls=[n.func for n in ast.walk(tree) if isinstance(n,ast.Call)]
    if any(isinstance(f,ast.Attribute) and f.attr=='step_task' or
           isinstance(f,ast.Name) and f.id=='GenericLLM' for f in calls):
        raise ValueError('qualification scope')
    out=dict(status='PASS',typed_configs=2,syntax_programs=4,plan_sha256=sha(ROOT/'plan.json'))
    write(ROOT/'cpu.json',out);print(json.dumps(out))

def submit():
    check();m=runtime()
    if read(ROOT/'cpu.json')['plan_sha256']!=sha(ROOT/'plan.json'): raise ValueError('preflight stale')
    if sha(m.infra.TASK_IMAGE)!=m.infra.IMAGE_SHA: raise ValueError('image drift')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    q=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True).split()
    if set(q)-{'12535'}: raise ValueError('unexpected active allocation')
    with (ROOT/'capacity.tmp').open('xb') as f: os.posix_fallocate(f.fileno(),0,256*1024**2)
    (ROOT/'capacity.tmp').unlink()
    write(ROOT/'submit-intent.json',dict(plan_sha256=sha(ROOT/'plan.json'),utc=m.utc()))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),
        '--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit(): raise RuntimeError('ambiguous submit; no retry')
    write(ROOT/'launch.json',dict(job=job,plan_sha256=sha(ROOT/'plan.json')))
    print(json.dumps(dict(job=job,status='SUBMITTED',gpu_hours_cap=1)))

def worker(i):
    check();m=runtime();ep=ROOT/f'episode-{i}'
    own=m.infra.native_uuids(1)
    os.environ.update(DOJO_GPU_UUIDS=own[0],DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{i}',
        PATH=str(ROOT/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own))
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{i}.json')
    Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    code=read(ROOT/'starts'/f'{i}.private.json')['code'];diag=diagnostic(i)
    deadline=ExperimentDeadline(1600)
    with deadline.activate():
        for trial,seed in enumerate(SEEDS):
            payloads=[];rows=[]
            for arm in range(2):
                action=ep/f'action-{trial*2+arm}';(action/'work').mkdir(parents=True)
                os.environ['FEEDBACK_ACTION_ROOT']=str(action)
                icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=300
                icfg.env['PYTHONHASHSEED']=str(seed)
                interp=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
                executable=f'import random, numpy as np\nrandom.seed({seed})\nnp.random.seed({seed})\nexec(compile({code!r},"parent.py","exec"))\n'
                try:
                    begin=time.monotonic();out=interp.run(executable,reset_session=False)
                    initial_seconds=time.monotonic()-begin
                    if out.exit_code or out.timed_out: raise RuntimeError('initial program failed')
                    query_begin=time.monotonic();qout=interp.run(diag,reset_session=False)
                    query_seconds=time.monotonic()-query_begin
                    if qout.exit_code or qout.timed_out: raise RuntimeError('query failed')
                    terminal='\n'.join(qout.term_out or [])
                    matches=[x.removeprefix('REUSE_RECEIPT ') for x in terminal.splitlines() if x.startswith('REUSE_RECEIPT ')]
                    if len(matches)!=1: raise ValueError('missing public receipt')
                    payload=json.loads(matches[0]);payloads.append(payload)
                    write(action/'public-diagnostic.json',payload)
                finally:
                    closed=time.monotonic();interp.close();close_seconds=time.monotonic()-closed
                row=dict(task=cfg.task.name,trial=trial,seed=seed,arm='retained' if arm==0 else 'recomputed',
                    initial_seconds=initial_seconds,query_seconds=query_seconds,close_seconds=close_seconds,
                    total_seconds=time.monotonic()-begin,query_sha256=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest(),
                    commit=COMMIT,plan_sha256=sha(ROOT/'plan.json'))
                write(action/'result.json',row);rows.append(row)
            write(ep/f'pair-{trial}.json',dict(task=cfg.task.name,seed=seed,exact_equal=payloads[0]==payloads[1],
                warm_marginal_seconds=rows[0]['query_seconds'],cold_total_seconds=rows[1]['total_seconds'],
                warm_initial_seconds=rows[0]['initial_seconds'],rows=rows))
    write(ep/'completed.json',dict(status='complete'))

def controller():
    check();m=runtime();job=os.environ['SLURM_JOB_ID']
    if read(ROOT/'launch.json')['job']!=job: raise ValueError('allocation mismatch')
    def run(i):
        ep=ROOT/f'episode-{i}'
        cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1',
             '--time=00:28:00',str(PY),'-B',str(ROOT/'state_reuse_qualification_20261002.py'),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:
            r=subprocess.run(cmd,env=m.infra.clean_env(),stdout=f,stderr=f,timeout=1690)
        write(ep/'closed.json',dict(returncode=r.returncode))
        return r.returncode
    with ThreadPoolExecutor(max_workers=2) as pool: codes=list(pool.map(run,range(2)))
    write(ROOT/'closed.json',dict(returncodes=codes,utc=m.utc()))
    if any(codes): raise RuntimeError('worker failure')

if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','cpu','submit','controller','worker','check']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode=='worker': worker(x.index)
    else: globals()[x.mode]()
