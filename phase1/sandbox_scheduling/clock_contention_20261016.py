"""Eight immutable real-program replays: solo / colocated / colocated / solo.

Mechanism only: fixed source, input, RNG and instrumentation. No generation,
training of the agent, output-dependent selection, or E2E benefit claim.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import traceback

D=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261016-v3')
R=D.parent/'clock-contention-20261016-v2'
PIN='a7cc9780c927cdeac3fc1effb214643a387353122e1fa542d3a40116b248d477'
PY=D.parent/'venvs/aira/bin/python'
NAME=Path(__file__).name
CAP=2700
TASKS=('aerial-cactus-identification','denoising-dirty-documents')

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,value):
    with Path(p).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False)
def schedule():
    return [dict(index=2*b+k,block=b,program=k,mode=mode,repeat=b//2,task=TASKS[k])
            for b,mode in enumerate(('solo','colocated','colocated','solo')) for k in range(2)]
def gateway_port(job,program):
    assert program in (0,1)
    return 41000+(int(job)%1000)*2+program
def port_hook(job,program):
    import dojo.core.interpreters.jupyter.jupyter_interpreter as native
    native._gateway_port=lambda:gateway_port(job,program)
def setup():
    sys.path.insert(0,str(D/'source/src'));sys.path.insert(1,str(D))
    spec=importlib.util.spec_from_file_location('clock_old_runtime',D/'runtime.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.R=D;m.setup()
    os.environ['LOGGING_DIR']=str(R)
    return m
def executable(code,seed):
    from image_gpu_observation_20261011 import INSTRUMENT,RECEIPT
    return ('import sys;sys.argv=["candidate.py"]\nimport torch\ntorch.manual_seed('+str(seed)+')\n'
        +INSTRUMENT+'\n'+f'import random as _r, numpy as _n\n_r.seed({seed})\n_n.random.seed({seed})\n'
        +code+'\n'+RECEIPT)
def select():
    from closed_clock_screen_20261016 import screen
    from dojo.utils.code_parsing import extract_code
    selected=[]
    plan=read(D/'plan.json')
    for task in TASKS:
        found=None
        for row in sorted(plan['schedule'],key=lambda r:r['index']):
            if row['task']!=task:continue
            ep=D/f"episode-{row['index']}"
            for p in sorted(ep.glob('candidate-*.json'),key=lambda p:int(p.name.split('-')[1].split('.')[0])):
                if '.private.' in p.name:continue
                c=read(p)
                if not(c['elapsed_seconds']<=1020 and c['valid'] is True and c['exit_code']==0 and not c['timed_out']):continue
                source=p.with_name(p.stem+'.private.json');code=read(source)['code']
                assert hashlib.sha256(code.encode()).hexdigest()==c['code_sha256']
                s=screen(code)
                if s.get('credential_shape_hit'):raise ValueError('credential shape: stop without echo')
                if not s.get('clock_exit_guards'):continue
                submitted=c['aux']['submission_sha256']
                observed=[]
                for q in ep.glob('scored-*.json'):
                    if read(q)['receipt']['submission_sha256']==submitted:
                        training=ep/('gpu-training-'+q.stem.split('-')[1]+'.json')
                        if training.exists():observed.append(training)
                if len(observed)!=1 or read(observed[0]).get('cuda_gradient_steps',0)<=0:continue
                action=executable(code,row['seed'])
                h=hashlib.sha256(extract_code(action).encode()).hexdigest()
                assert h==c['aux']['executed_code_sha256'],'original executable reconstruction drift'
                found=dict(task=task,source_episode=row['index'],source_candidate=int(p.stem.split('-')[1]),
                    seed=row['seed'],code_sha256=c['code_sha256'],executed_sha256=h,
                    original_config_sha256=sha(D/f"configs/{row['index']}.json"),
                    evidence_sha256=sha(p),gpu_observation_sha256=sha(observed[0]),code=code,action=action)
                break
            if found is not None:break
        if found is None:raise ValueError('no eligible fixed program for '+task)
        selected.append(found)
    return selected

def prepare(commit):
    assert re.fullmatch('[a-f0-9]{40}',commit) and sha(D/'plan.json')==PIN
    assert read(D/'readout-20261016-v1/summary.json')['complete']==32
    old=read(D/'plan.json')
    for n,h in old['files'].items():assert sha(D/n)==h,'closed donor source drift'
    m=setup();chosen=select()
    # No directory or execution is created until the two chronological choices
    # and their exact original executable hashes have passed.
    R.mkdir(mode=0o700);(R/'configs').mkdir();(R/'bin').mkdir();(R/'programs').mkdir()
    for name in (NAME,'closed_clock_screen_20261016.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    for k,p in enumerate(chosen):
        (R/f'programs/{k}.private.py').write_text(p.pop('action'))
        p.pop('code')
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from unittest.mock import patch
    port_hook('100',0)
    for row in schedule():
        ep=R/f"episode-{row['index']}";(ep/'work/input_cache').mkdir(parents=True)
        p=chosen[row['program']];cfg=read(D/f"configs/{p['source_episode']}.json")
        original=str(D/f"episode-{p['source_episode']}")
        cfg=json.loads(json.dumps(cfg).replace(original,str(ep)))
        cfg['id']=f"clock-{row['index']}"
        cfg['logger']['output_dir']=str(ep/'native-log')
        assert cfg['interpreter']['timeout']==300
        assert cfg['interpreter']['env']['PYTHONHASHSEED']==str(p['seed'])
        write(R/f"configs/{row['index']}.json",cfg)
        c=RunConfig.load_from_json(R/f"configs/{row['index']}.json");c.validate()
        assert not Path(c.task.private_dir).exists()
        assert not c.logger.write_env_vars and not c.logger.use_wandb
        port_hook('100',row['program'])
        factory=build(c.interpreter,INTERPRETER_MAP,data_dir=c.task.data_dir)
        assert factory.factory
        # Native constructor starts its server immediately. Substitute ONLY
        # that external launcher in CPU preparation, never in production.
        with patch('dojo.core.interpreters.jupyter.jupyter_interpreter.SingularityJupyterServer') as server:
            assert factory.instance.port==gateway_port('100',row['program'])
            assert factory.instance.timeout==300
            assert server.call_args.kwargs['port']==gateway_port('100',row['program'])
            factory.close()
    shim=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import task_runtime\ntask_runtime()\n'
    (R/'bin/singularity').write_text(shim);os.chmod(R/'bin/singularity',0o700)
    (R/'run.sbatch').write_text(f'''#!/bin/bash
#SBATCH --job-name=r14-clock-contention
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --hint=nomultithread
#SBATCH --time=00:45:00
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec srun --exclusive --ntasks=1 --cpus-per-task=4 --gres=gpu:1 {PY} -B {R/NAME} run
''')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not p.relative_to(R).parts[0].startswith('episode-')}
    write(R/'plan.json',dict(source_commit=commit,donor_plan_sha256=PIN,donor_files=old['files'],files=files,
        schedule=schedule(),programs=chosen,task_image=str(m.TASK_IMAGE),task_image_sha256=old['task_image_sha256'],
        allocation_seconds=CAP,gpus=1,node='gpu27',worker_seconds=380,execution_seconds=300,
        selection='First chronological valid, clock-guard, observed CUDA-gradient program per task; no score ranking.',
        primary='All8 fixed-source executions, optimizer steps, output hashes/differences, pristine DEV score; within-arm repeat noise. Not E2E.',
        stop='Any infrastructure/namespace/cleanup or first solo valid-CUDA failure stops remaining; no replacements/retries.'))
    print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),programs=chosen)))

def check():
    p=read(R/'plan.json');assert p['schedule']==schedule() and sha(D/'plan.json')==PIN
    for n,h in p['files'].items():assert sha(R/n)==h,'new source drift'
    for n,h in p['donor_files'].items():assert sha(D/n)==h,'donor drift'
    return p
def task_runtime():
    setup()
    from pooling_trial_20261015 import namespace_command
    from forets_gpu_binding_20260911 import REAL_SINGULARITY
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    ep=Path(os.environ['POLICY9B_EPISODE']);assert ep.parent==R and re.fullmatch(r'episode-[0-7]',ep.name)
    n=read(R/'native.json');assert n['job']==os.environ['SLURM_JOB_ID'] and n['step']==os.environ['SLURM_STEP_ID']
    from resource_gpu_identity import gpu_uuids
    assert gpu_uuids(1)==n['gpu_uuids']
    cmd,env,receipt=namespace_command(args,n['gpu_uuids'][0])
    write(ep/f'binding-{os.getpid()}.json',dict(receipt,wall=time.time()))
    os.execve(REAL_SINGULARITY,cmd,env)

def worker(index):
    p=check();setup();row=schedule()[index];n=read(R/'native.json');ep=R/f'episode-{index}'
    os.sched_setaffinity(0,n['cpu_slots'][row['program']]);uid=n['gpu_uuids'][0]
    os.environ.update(CUDA_VISIBLE_DEVICES=uid,DOJO_GPU_UUIDS=uid,POLICY9B_EPISODE=str(ep),
        DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        DOJO_EXECUTION_ID=f"{n['job']}.{n['step']}:{index}",PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.utils.experiment_deadline import ExperimentDeadline,ExperimentDeadlineExpired
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,AUX_EVAL_INFO
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),
        host_boot_id=_host_boot_id(),gpu_uuids=[uid],container_pid=None,container_process_start_ticks=None))
    deadline=ExperimentDeadline(350);task=None;state=None;interp=None;error=None;result={}
    try:
        with deadline.activate():
            cfg=RunConfig.load_from_json(R/f'configs/{index}.json');cfg.interpreter.env['CUDA_VISIBLE_DEVICES']=uid
            cfg.validate();config_logger(cfg)
            port_hook(n['job'],row['program'])
            task=MLEBenchTask(cfg.task);interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
            assert interp.factory
            state,_=task.prepare(solver_interpreter=interp,eval_interpreter=None)
            original_score=task._search_only_score
            def capture(name,submission):
                receipt=original_score(name,submission)
                shutil.copyfile(submission,ep/'prediction.private.csv');write(ep/'score.json',receipt)
                training=Path(interp.working_dir)/'gpu_training.json'
                if not interp.fetch_file(training):raise RuntimeError('missing training observation')
                write(ep/'gpu-training.json',read(training))
                return receipt
            task._search_only_score=capture
            action=(R/f"programs/{row['program']}.private.py").read_text()
            write(ep/'started.json',dict(wall=time.time(),index=index,cpu_affinity=sorted(os.sched_getaffinity(0))))
            state,answer=task.step_task(state,action);out=answer[EXECUTION_OUTPUT]
            result=dict(valid=bool(answer.get(VALID_SOLUTION)),exit_code=out.exit_code,timed_out=out.timed_out,
                exec_seconds=out.exec_time,executed_sha256=answer.get(AUX_EVAL_INFO,{}).get('executed_code_sha256'))
            assert result['executed_sha256']==p['programs'][row['program']]['executed_sha256']
    except BaseException as exc:
        error=dict(type=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    finally:
        if interp is not None:
            try:interp.close()
            except BaseException as exc:error=error or dict(type=type(exc).__name__,phase='close')
        write(ep/'finished.json',dict(row,**result,error=error,elapsed_seconds=deadline.elapsed(),wall=time.time()))
    return int(error is not None)

def run():
    p=check();setup();start=time.monotonic();error=None;records=[]
    from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology
    from live_search_trial_20261009 import owned_cleanup,gpu_sample,process_gone
    assert socket.gethostname().split('.')[0]==p['node']
    cpus={}
    for r in cpu_topology():cpus.setdefault((r['socket'],r['core']),[]).append(r['logical_cpu'])
    cores=sorted(min(v) for v in cpus.values());assert len(cores)==4
    own=gpu_uuids(1);assert not gpu_sample(own[0])['pids']
    write(R/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
        gpu_uuids=own,cpu_slots=[cores[:2],cores[2:]],wall=time.time()))
    def execute(indices):
        ps=[];logs=[];launch=time.monotonic()
        try:
            for i in indices:
                ep=R/f'episode-{i}';f=(ep/'worker.private.log').open('xb');logs.append(f)
                proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(i)],stdout=f,stderr=f,start_new_session=True)
                ps.append((i,proc))
            while any(proc.poll() is None for _,proc in ps):
                if time.monotonic()-launch>380:raise TimeoutError('worker group cap')
                if time.monotonic()-start>CAP-60:raise TimeoutError('allocation reserve')
                time.sleep(.5)
        finally:
            for i,proc in ps:
                ep=R/f'episode-{i}'
                owned_cleanup(proc,ep)
                identity=read(ep/'identity.json') if (ep/'identity.json').exists() else {}
                clean=bool(identity) and all(process_gone(identity.get(a),identity.get(b)) for a,b in
                    (('pid','process_start_ticks'),('container_pid','container_process_start_ticks')))
                records.append(dict(index=i,returncode=proc.poll(),cleanup=clean))
            for f in logs:f.close()
        assert all(x['returncode']==0 and x['cleanup'] for x in records),'worker/cleanup failed'
        assert not gpu_sample(own[0])['pids'],'owned GPU not clean after group'
    try:
        for b,mode in enumerate(('solo','colocated','colocated','solo')):
            indices=[2*b,2*b+1] if b<2 else [2*b+1,2*b]
            if mode=='solo':
                for i in indices:execute([i])
            else:execute(indices)
            if b==0:
                assert all(read(R/f'episode-{i}/finished.json').get('valid') and read(R/f'episode-{i}/gpu-training.json')['cuda_gradient_steps']>0 for i in indices)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    finally:
        write(R/'closed.json',dict(planned=8,records=records,error=error,elapsed_seconds=time.monotonic()-start,
            cleanup_verified=not gpu_sample(own[0])['pids']))
    return int(error is not None)

def submit():
    p=check();assert sha(Path(p['task_image']))==p['task_image_sha256']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not (R/'submit-intent.json').exists()
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),wall=time.time()))
    out=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.private.out'),
        '--error='+str(R/'allocation-%j.private.err'),str(R/'run.sbatch')],env=env,text=True,capture_output=True,timeout=25)
    job=out.stdout.strip().split(';')[0]
    if out.returncode or not job.isdigit():raise RuntimeError('ambiguous submit; do not repeat')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,plan_sha256=sha(R/'plan.json'))))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=('inspect','prepare','submit','run','worker'))
    a.add_argument('--commit');a.add_argument('--index',type=int);v=a.parse_args()
    if v.action=='inspect':
        setup();print(json.dumps([{k:v for k,v in p.items() if k not in ('code','action')} for p in select()]))
    elif v.action=='prepare':prepare(v.commit)
    elif v.action=='submit':submit()
    elif v.action=='worker':sys.exit(worker(v.index))
    else:sys.exit(run())
