"""Frozen causal control: parallel startup versus parallel candidate execution.

Four unchanged public-development programs, three policies, three source-seed
restarts. 36 slots + warmup, one 3090 / six CPUs / <=45min all-in.
No source edits, shared candidate cache, score, API or agent-base training.
"""
import argparse
import concurrent.futures as cf
import csv
import functools
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

import entry_recheck as entry
from entry_contract import setup_cell
from lifecycle_pilot import read,write,sha

B=Path('/research/d7/spc/yzyang4')
D=B/'scheduling-pool-20261008-v2'
R=B/'scheduling-pipeline-20261008-v1'
PY=B/'venvs/aira/bin/python'
NAME='pipeline_trial.py'
PROGRAMS=(0,1,4,3)
ARMS=('serial','pipeline','share2')
DONOR='429339013cca8e2858cb2cc2edfefe017f096b0c4afbc0172987d897becf7a56'


def schedule():
    result=[]
    for repeat in range(3):
        order=PROGRAMS[repeat:]+PROGRAMS[:repeat]
        for arm in ARMS[repeat:]+ARMS[:repeat]:
            for position,program in enumerate(order):
                result.append(dict(index=len(result),program=program,arm=arm,repeat=repeat,
                                   position=position,source_seed=42,harness_seed=130701))
    return result


def predecessor(row):
    return row['index']-1 if row['arm']=='pipeline' and row['position'] else None


@functools.lru_cache(maxsize=1)
def pilot():
    entry.R=R;entry.schedule=schedule
    return entry.pilot()


def check():
    plan=read(R/'plan.json')
    if plan['schedule']!=schedule() or plan['gpu_hours_cap']!=.75:
        raise ValueError('plan contract')
    for name,pin in plan['files'].items():
        if sha(R/name)!=pin:raise ValueError('frozen file drift')
    for path,pin in plan['input_files'].items():
        if sha(path)!=pin:raise ValueError('input drift')
    return plan


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or sha(D/'plan.json')!=DONOR:
        raise ValueError('donor/source pin')
    if not (D/'closed.json').exists():raise ValueError('donor not closed')
    old=read(D/'plan.json');R.mkdir(mode=0o700,exist_ok=False)
    copied=('runtime.py','throughput_pilot.py','entry_recheck.py','entry_contract.py','lifecycle_pilot.py','census.py')
    for name,pin in old['files'].items():
        if not(name.startswith(('source/','forets_','opencl-vendors/','programs/')) or name in copied):continue
        if sha(D/name)!=pin:raise ValueError('donor file drift')
        dest=R/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dest)
    for name in (NAME,'pipeline_readout.py','throughput_readout.py','verify_pool_outputs.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    programs=old['programs']
    inputs={}
    for i in PROGRAMS:
        directory=Path(programs[i]['data'])
        for p in directory.iterdir():
            if p.is_file():inputs[str(p)]=sha(p)
    (R/'empty-data').mkdir();(R/'bin').mkdir()
    for i in range(37):(R/f'episode-{i}/work').mkdir(parents=True)
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom pipeline_trial import pilot\npilot().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    batch=(D/'run.sbatch').read_text().replace('r14-pool-v2','r14-pipeline-v1').replace(str(D),str(R)).replace('01:30:00','00:45:00').replace('5350s','2650s').replace('fixed_pool_trial.py controller',f'{NAME} controller')
    (R/'run.sbatch').write_text(batch)
    plan=dict(source_commit=commit,donor_plan_sha256=DONOR,schedule=schedule(),programs=programs,
              node='gpu27',gpus=1,total_cpu=6,gpu_hours_cap=.75,allocation_seconds=2700,
              planned_executions=36,worker_hard_seconds=330,candidate_timeout_seconds=120,
              interpreter_deadline_seconds=300,queue_wait_cap_seconds=180,
              single_change='serial complete workers / two cold initializations but FIFO serial candidates through close / two complete concurrent workers',
              new_batch_not_repair_of_16994=True,shared_candidate_cache=False,source_changes=False,
              first_serial_gate='all four complete including both GPU fits, otherwise stop',
              later_failure='retain every failed slot; never retry; stop expansion if isolation/release fails',
              decision='Three complete paired blocks per comparison, all nine outputs/program exactly equal; median ratio >=1.05 is exploratory system benefit, not novelty or E2E',
              primary='pipeline versus share2 separates overlap of initialization from candidate execution; original serial is control',
              source_seed=42,harness_seed=130701,repeat_unit='same-source-seed restart, not independent training seed',
              no_api=True,no_base_model_update=True,no_quality_scoring=True,input_files=inputs,
              files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()})
    write(R/'plan.json',plan)
    m=pilot().runtime()
    image=sha(m.TASK_IMAGE)
    if image!='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda':raise ValueError('image drift')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),image_sha256=image,
                                no_candidate_execution=True,unchanged_donor_inputs=True))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'))))


def wait_turn(row,ep):
    previous=predecessor(row)
    ready=time.time();write(ep/'prelude_ready.json',dict(time=ready,predecessor=previous))
    if previous is not None:
        path=R/f'episode-{previous}/closed.json'
        # The marker appears only after the immutable JSON has fully closed.
        # Existence of the JSON alone would race its first write.
        marker=path.with_name('closed.ready')
        while not marker.exists():
            if time.time()-ready>180:raise TimeoutError('pipeline predecessor wait')
            time.sleep(.02)
        if read(path)['returncode']!=0:raise ValueError('failed pipeline predecessor')
    write(ep/'execution_admitted.json',dict(time=time.time()))


def worker(index):
    p=pilot();m=p.runtime();plan=read(R/'plan.json');ep=R/f'episode-{index}'
    warm=index==36;row=dict(index=36,arm='warmup') if warm else schedule()[index]
    source=None if warm else plan['programs'][row['program']]
    gpu=m.infra().native_uuids(1)[0]
    os.environ.update(DOJO_GPU_UUIDS=gpu,POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.experiment_deadline import ExperimentDeadline
    import dojo.core.interpreters.jupyter.jupyter_interpreter as ji
    ji._slurm_gateway_port=lambda:31000+(int(os.environ['SLURM_JOB_ID'])%400)*40+index
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=[gpu]))
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=[gpu],container_pid=None,container_process_start_ticks=None))
    cfg=JupyterInterpreterConfig(working_dir=str(ep/'work'),timeout=120,container_runtime='singularity',superimage_directory=str(m.TASK_IMAGE.parent),superimage_version='2026-07-macos-v1',
        read_only_binds={source['data']:'/workspace/workspace_input'} if source else {},
        env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'6','OPENBLAS_NUM_THREADS':'6','MKL_NUM_THREADS':'6','PYTHONHASHSEED':'130701'})
    interp=None;error=None;metrics={};start=time.time();stage=0
    write(ep/'started.json',dict(**row,start=start,affinity=sorted(os.sched_getaffinity(0))))
    def invoke(code,**kwargs):
        nonlocal stage
        begin=time.time();n=stage;stage+=1;result=interp.run(code,**kwargs)
        write(ep/f'cell-{n}.json',entry.cell_receipt(result,n,begin,time.time()))
        (ep/f'cell-{n}.private.txt').write_text('\n'.join(map(str,result.term_out)))
        return result
    try:
        with ExperimentDeadline(300).activate():
            interp=build(cfg,INTERPRETER_MAP,data_dir=source['data'] if source else R/'empty-data')
            if source:
                result=invoke(setup_cell(130701,p.GPU_INSTRUMENT if source['expected_gpu'] else ''))
                if result.exit_code or result.timed_out:raise ValueError('setup failed')
                wait_turn(row,ep)
            write(ep/'candidate_started.json',dict(time=time.time()))
            result=invoke((R/f'programs/{row["program"]}.py').read_text() if source else p.WARMUP,reset_session=warm)
            write(ep/'candidate_ended.json',dict(time=time.time()))
            metrics.update(exit_code=result.exit_code,timed_out=result.timed_out,exec_seconds=result.exec_time)
            if result.exit_code or result.timed_out:raise RuntimeError('candidate failed')
            name='submission.csv' if source else 'environment.json'
            if not interp.fetch_file(ep/'work'/name):raise ValueError('missing output')
            metrics['output']=p.output_structure(ep/'work'/name,Path(source['data'])/'test.csv') if source else read(ep/'work'/name)
            if source and source['expected_gpu']:
                result=invoke(p.GPU_RECEIPT,reset_session=False)
                if result.exit_code or result.timed_out or not interp.fetch_file(ep/'work/gpu_training.json'):raise ValueError('GPU fit absent')
                metrics['gpu_training']=read(ep/'work/gpu_training.json')
    except Exception as exc:error=type(exc).__name__
    finally:
        if interp is not None:
            try:interp.close()
            except Exception as exc:error=error or type(exc).__name__
        write(ep/'completed.json',dict(**row,**metrics,error_type=error,complete=error is None,start=start,end=time.time(),source_commit=plan['source_commit']))
    return 1 if error else 0


def run_one(index):
    ep=R/f'episode-{index}';start=time.time()
    with (ep/'worker.private.log').open('xb') as out:
        proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(index)],stdout=out,stderr=out,start_new_session=True)
        try:rc=proc.wait(timeout=330)
        except subprocess.TimeoutExpired:pilot().terminate_owned(proc,ep);rc=124
    write(ep/'closed.json',dict(returncode=rc,start=start,end=time.time()))
    (ep/'closed.ready').touch(exist_ok=False)
    return dict(index=index,returncode=rc,complete=rc==0 and read(ep/'completed.json')['complete'])


def controller():
    plan=check();p=pilot();m=p.runtime();start=time.time();error=None
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':raise ValueError('allocation identity')
    gpu=m.infra().native_uuids(1)[0]
    write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,start=start,affinity=sorted(os.sched_getaffinity(0))))
    try:
        if p.gpu_sample(gpu)['apps']:raise ValueError('baseline GPU client')
        if not run_one(36)['complete'] or p.gpu_sample(gpu)['apps']:raise ValueError('warmup/release')
        for b in range(9):
            rows=schedule()[4*b:4*b+4];arm=rows[0]['arm'];width=1 if arm=='serial' else 2
            if time.time()-start+4*335>2610:raise TimeoutError('whole block budget')
            if p.gpu_sample(gpu)['apps']:raise ValueError('preblock release')
            samples=[];errors=[];stop=threading.Event()
            def observe():
                while not stop.is_set():
                    try:samples.append(p.gpu_sample(gpu))
                    except Exception as exc:errors.append(type(exc).__name__);break
                    stop.wait(.5)
            observer=threading.Thread(target=observe,daemon=True);begin=time.time();observer.start()
            try:
                with cf.ThreadPoolExecutor(max_workers=width) as pool:outcomes=list(pool.map(run_one,[r['index'] for r in rows]))
            finally:stop.set();observer.join(timeout=10)
            write(R/f'block-{b}.json',dict(block=b,arm=arm,repeat=rows[0]['repeat'],start=begin,end=time.time(),outcomes=outcomes,telemetry_errors=errors))
            write(R/f'telemetry-{b}.json',samples)
            if errors or observer.is_alive() or p.gpu_sample(gpu)['apps']:raise ValueError('telemetry/release')
            if b==0 and not all(o['complete'] for o in outcomes):raise ValueError('first serial qualification')
    except Exception as exc:error=type(exc).__name__
    finally:
        runs=[]
        for row in schedule():
            ep=R/f'episode-{row["index"]}';item=dict(**row,status='not_started',source_commit=plan['source_commit'])
            if (ep/'started.json').exists():item['status']='incomplete'
            if (ep/'closed.json').exists():item.update(read(ep/'closed.json'));item['status']='failed'
            if (ep/'completed.json').exists():
                done=read(ep/'completed.json');item.update({k:v for k,v in done.items() if k not in ('output','gpu_training')})
                item['status']='complete' if done['complete'] and item.get('returncode')==0 else 'failed'
                item['output_sha256']=done.get('output',{}).get('sha256')
            runs.append(item)
        write(R/'closed.json',dict(planned=36,attempted=sum(r['status']!='not_started' for r in runs),completed=sum(r['status']=='complete' for r in runs),error_type=error,elapsed_seconds=time.time()-start))
        write(R/'runs.json',runs)
        with (R/'runs.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted({k for r in runs for k in r}));w.writeheader();w.writerows(runs)
    return 1 if error or any(r['status']!='complete' for r in runs) else 0


def submit():
    check()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
    env=pilot().runtime().infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=.75))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=.75)))


if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','controller','worker']);ap.add_argument('--commit');ap.add_argument('--index',type=int);args=ap.parse_args()
    if args.mode=='prepare':prepare(args.commit)
    elif args.mode=='worker':sys.exit(worker(args.index))
    else:sys.exit(globals()[args.mode]())
