"""Human-specified one-keyword control. Never count as autonomous agent benefit."""
import argparse,ast,copy,hashlib,importlib.util,json,os,shutil,subprocess,sys,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
B=Path('/research/d7/spc/yzyang4');PARENT=B/'state-feedback-factorial-20261002-v1'
ROOT=B/'char-branch-control-20261003-v1';PY=B/'venvs/aira/bin/python'
COMMIT='93c9246970865d0fe48a85e2b564ad62ca837947';SEEDS=(103701,103702)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def runtime():
    p=ROOT/'v6_runtime.py';assert sha(p)=='4b155d927c12f063e0838b5708085fe1bc55c4983197a3d8d2453696d73c55ad'
    s=importlib.util.spec_from_file_location('char_control_runtime',p);m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
    m.ROOT=ROOT;m.infra.ROOT=ROOT;m.setup();return m
def changed(code):
    needle='tfidf_char = TfidfVectorizer(\n'
    assert code.count(needle)==1
    candidate=code.replace(needle,needle+'    analyzer="char",\n')
    tree=ast.parse(candidate)
    node=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='tfidf_char' for t in n.targets))
    kw=[k for k in node.value.keywords if k.arg=='analyzer'];assert len(kw)==1 and kw[0].value.value=='char'
    node.value.keywords.remove(kw[0]);assert ast.dump(tree)==ast.dump(ast.parse(code))
    return candidate
def check():
    p=read(ROOT/'plan.json')
    for f,h in p['files'].items():assert sha(ROOT/f)==h,f
    return p
def prepare():
    if ROOT.exists():raise FileExistsError(ROOT)
    assert sha(PARENT/'plan.json')=='2820d6cc64d9d1045179f2290383340c38605b6ba604364d8fd6307be2a0b237'
    p=read(PARENT/'plan.json');ROOT.mkdir(mode=0o700)
    for rel,h in p['files'].items():
        if not(rel.startswith(('source/','forets_','opencl-vendors/')) or rel=='v6_runtime.py'):continue
        assert sha(PARENT/rel)==h
        target=ROOT/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PARENT/rel,target)
    shutil.copyfile(__file__,ROOT/Path(__file__).name)
    (ROOT/'bin').mkdir();(ROOT/'configs').mkdir();(ROOT/'starts').mkdir()
    code=read(PARENT/'starts/0.private.json')['code'];new=changed(code)
    write(ROOT/'starts/original.private.json',dict(code=code));write(ROOT/'starts/char.private.json',dict(code=new))
    wrapper=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(ROOT)!r})\nfrom char_branch_control_20261003 import runtime\nruntime().task_runtime()\n'
    (ROOT/'bin/singularity').write_text(wrapper);os.chmod(ROOT/'bin/singularity',0o700)
    for i,seed in enumerate(SEEDS):
        cfg=read(PARENT/'configs/0.json');(ROOT/f'episode-{i}').mkdir()
        cfg['id']=f'char-human-control-{i}';cfg['logger']['output_dir']=str(ROOT/f'episode-{i}/native-log')
        cfg['metadata'].update(seed=seed,base_path=str(ROOT/'source'),git_commit_id=COMMIT,script_id='char-branch-control-20261003')
        cfg['interpreter']['env']['PYTHONHASHSEED']=str(seed);cfg['task']['cache_dir']=str(ROOT/'no-official-data')
        write(ROOT/'configs'/f'{i}.json',cfg)
    batch=f'''#!/bin/bash
#SBATCH --job-name=char-human-control
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
timeout --signal=TERM --kill-after=20s 1740s {PY} -B {ROOT}/char_branch_control_20261003.py controller
'''
    (ROOT/'run.sbatch').write_text(batch)
    files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file()}
    write(ROOT/'plan.json',dict(protocol='char-human-control-v1',commit=COMMIT,files=files,seeds=SEEDS,
        code_sha256={a:hashlib.sha256(c.encode()).hexdigest() for a,c in [('original',code),('char',new)]},
        tasks=['random-acts-of-pizza'],executions=4,execution_cap=300,allocation_seconds=1800,gpus=2,gpu_hours_cap=1,
        paid_api=0,generator_calls=0,agent_training=False,protected_opened=False,
        source='historical incumbent, parent code unchanged except analyzer=char in tfidf_char assignment',
        order=[['original','char'],['char','original']],endpoint='each seed char-minus-original external development AUC; median and sample variance; report both public OOF and external scores',
        interpretation='manual one-keyword opportunity diagnostic, not an automatic method, not final evaluation, not a guaranteed positive control'))
    cpu()
def cpu():
    p=check();m=runtime();from dojo.config_dataclasses.run import RunConfig
    assert changed(read(ROOT/'starts/original.private.json')['code'])==read(ROOT/'starts/char.private.json')['code']
    for i in range(2):
        c=RunConfig.load_from_json(ROOT/'configs'/f'{i}.json');c.validate();assert not Path(c.task.private_dir).exists()
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    out=dict(status='PASS',single_keyword_ast_difference=True,typed_configs=2,plan_sha256=sha(ROOT/'plan.json'))
    write(ROOT/'cpu.json',out);print(json.dumps(out))
def submit():
    check();m=runtime();assert not (ROOT/'submit-intent.json').exists()
    assert read(ROOT/'cpu.json')['plan_sha256']==sha(ROOT/'plan.json') and sha(m.infra.TASK_IMAGE)==m.infra.IMAGE_SHA
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=25).split();assert not set(jobs)-{'12535','15282'}
    with (ROOT/'capacity.tmp').open('xb') as f:os.posix_fallocate(f.fileno(),0,256*1024**2)
    (ROOT/'capacity.tmp').unlink();write(ROOT/'submit-intent.json',dict(utc=m.utc(),plan_sha256=sha(ROOT/'plan.json')))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(ROOT),'--output='+str(ROOT/'allocation-%j.out'),'--error='+str(ROOT/'allocation-%j.err'),str(ROOT/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(ROOT/'launch.json',dict(job=job,plan_sha256=sha(ROOT/'plan.json')));print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=1)))
def worker(i):
    check();m=runtime();ep=ROOT/f'episode-{i}';seed=SEEDS[i];own=m.infra.native_uuids(1)
    os.environ.update(DOJO_GPU_UUIDS=own[0],DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),DOJO_EXECUTION_ID=f'{os.environ["SLURM_JOB_ID"]}.{os.environ["SLURM_STEP_ID"]}:{i}',PATH=str(ROOT/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.tasks.mlebench.task import MLEBenchTask
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own))
    cfg=RunConfig.load_from_json(ROOT/'configs'/f'{i}.json');Path(cfg.logger.output_dir).mkdir();config_logger(cfg)
    task=MLEBenchTask(cfg.task);assert task._search_only_score and not task.private_dir.exists()
    with ExperimentDeadline(1600).activate():
        for step,arm in enumerate(read(ROOT/'plan.json')['order'][i]):
            action=ep/f'action-{step}';(action/'work').mkdir(parents=True);os.environ['FEEDBACK_ACTION_ROOT']=str(action)
            icfg=copy.deepcopy(cfg.interpreter);icfg.working_dir=str(action/'work');icfg.timeout=300
            interp=build(icfg,INTERPRETER_MAP,data_dir=cfg.task.data_dir);code=read(ROOT/'starts'/f'{arm}.private.json')['code']
            tail="\nprint('CHAR_CONTROL_PUBLIC '+json.dumps({'analyzer':tfidf_char.analyzer,'blend_auc':float(blend_auc),'model_aucs':{k:float(v) for k,v in aucs.items()}}))\n"
            executable=f'import random, numpy as np\nrandom.seed({seed})\nnp.random.seed({seed})\nexec(compile({(code+tail)!r},"program.py","exec"))\n'
            began=time.monotonic();metric=None;receipt=None;pub=None
            try:
                out=interp.run(executable,reset_session=False);terminal='\n'.join(out.term_out or [])
                if m.SECRET.search(terminal.encode()):raise ValueError('credential-shaped output')
                write(action/'terminal.private.json',dict(terminal=terminal))
                if out.exit_code==0 and not out.timed_out:
                    lines=[v.removeprefix('CHAR_CONTROL_PUBLIC ') for v in terminal.splitlines() if v.startswith('CHAR_CONTROL_PUBLIC ')]
                    assert len(lines)==1;pub=json.loads(lines[0]);assert pub['analyzer']==('char' if arm=='char' else 'word')
                    sub=action/'work/submission.csv';interp.fetch_file(sub);assert sub.is_file() and not sub.is_symlink()
                    shutil.copyfile(sub,action/'submission.private.csv');receipt=task._search_only_score(cfg.task.name,sub)
                    write(action/'score-receipt.private.json',receipt);metric=receipt[task._search_only_metric_name]
            finally:interp.close()
            write(action/'result.json',dict(task=cfg.task.name,index=i,step=step,seed=seed,arm=arm,metric=metric,valid=metric is not None,
                exit_code=out.exit_code,timed_out=out.timed_out,seconds=time.monotonic()-began,public=pub,code_sha256=hashlib.sha256(code.encode()).hexdigest(),plan_sha256=sha(ROOT/'plan.json'),commit=COMMIT))
    write(ep/'completed.json',dict(status='complete'))
def controller():
    check();m=runtime();assert read(ROOT/'launch.json')['job']==os.environ['SLURM_JOB_ID']
    def run(i):
        ep=ROOT/f'episode-{i}';cmd=['srun','--exclusive','--nodes=1','--ntasks=1','--cpus-per-task=6','--gres=gpu:1','--time=00:28:00',str(PY),'-B',str(ROOT/'char_branch_control_20261003.py'),'worker','--index',str(i)]
        with (ep/'worker.private.log').open('xb') as f:r=subprocess.run(cmd,env=m.infra.clean_env(),stdout=f,stderr=f,timeout=1690)
        write(ep/'closed.json',dict(returncode=r.returncode));return r.returncode
    with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(run,range(2)))
    write(ROOT/'closed.json',dict(returncodes=codes,utc=m.utc()))
    if any(codes):raise RuntimeError('worker failure')
if __name__=='__main__':
    os.umask(0o077);a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','submit','controller','worker','check']);a.add_argument('--index',type=int);x=a.parse_args()
    if x.mode=='worker':worker(x.index)
    else:globals()[x.mode]()
