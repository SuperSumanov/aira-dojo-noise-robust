"""Independent fixed-program width1/2/4 challenge, max1.5 GPUh all-inclusive.

Four instances (two per existing neural program), three counterbalanced rounds,
36 assignments. This tests a cheap stronger baseline, not a semantic scheduler,
new task/seed generalization, or live-search quality. No replacement trials.
"""
import argparse
import concurrent.futures as cf
import csv
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

import neural_pool_trial as n
from bounded_readiness import wait_for_ready
from lifecycle_pilot import read,write,sha
from live_identity import cpu_topology,cores
from width_contract import schedule,may_admit,WIDTHS

R=Path('/research/d7/spc/yzyang4/scheduling-neural-width-20261009-v1')
D=R.parent/'scheduling-neural-qualified-overlap-20261008-evening-v1'
DONOR='c73cb9ce97ae092ee3bb4ea761201da22dc08d35dfa3f5ecf3aa34bdd8415abc'
NAME='neural_width_trial.py'
CAP=5400
CLIENT_SHA='a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'
HELPER_SHA='0fd8ead4c8eac2fc128b36d096ed15ceebeabc43a5fc5841d8c17e882ca381cd'


def configure():
    n.R=R;n.NAME=NAME;n.NODE='gpu27';n.CAP=CAP;n.schedule=schedule;n.write=boundary_write
    return n.pilot()


def boundary_write(path,value):
    if path.parent.parent==R and path.parent.name.startswith('episode-'):
        index=int(path.parent.name.removeprefix('episode-'))
        if path.name=='candidate_started.json' and index!=36:
            row=schedule()[index];block=row['block'];indices=list(range(block*4,block*4+4))
            write(path.parent/'prelude_ready.json',dict(time=time.time()))
            start=time.monotonic()
            import fcntl
            while True:
                if (R/f'abort-{block}.json').exists():raise RuntimeError('fixed block aborted; no replacement')
                if time.monotonic()-start>450:raise TimeoutError('admission budget')
                with (R/f'mutex-{block}').open('r+') as lock:
                    fcntl.flock(lock,fcntl.LOCK_EX)
                    ready={i for i in indices if (R/f'episode-{i}/prelude_ready.json').exists()}
                    admitted={i for i in indices if (R/f'episode-{i}/execution_admitted.json').exists()}
                    closed={i for i in indices if (R/f'episode-{i}/closed.ready').exists()}
                    if may_admit(index,indices,ready,admitted,closed,WIDTHS[row['arm']]):
                        write(path.parent/'execution_admitted.json',dict(time=time.time()))
                        value=dict(value,time=time.time())
                        return write(path,value)
                time.sleep(.05)
        if path.name=='closed.json' and index!=36:
            result=write(path,value)
            done=path.parent/'completed.json'
            if value['returncode']==0 and done.exists() and read(done)['complete'] is True:
                path.with_name('closed.ready').touch(exist_ok=False)
            return result
    return write(path,value)


def check():
    p=read(R/'plan.json')
    if p['schedule']!=schedule() or p['allocation_seconds']!=CAP or p['planned_executions']!=36:
        raise ValueError('frozen width matrix')
    for name,pin in p['files'].items():
        if sha(R/name)!=pin:raise ValueError('source drift')
    for name,pin in p['input_files'].items():
        if sha(name)!=pin:raise ValueError('input drift')
    return p


def batch_script():
    return f'''#!/bin/bash
#SBATCH --job-name=r14-width-challenge
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --hint=nomultithread
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 5350s srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --hint=nomultithread {n.PY} -B {R/NAME} controller
'''


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or sha(D/'plan.json')!=DONOR:
        raise ValueError('exact source/donor')
    old=read(D/'plan.json')
    if read(D/'closed.json')['completed']!=12:raise ValueError('completed donor required')
    # Existing candidate and worker remain unchanged; new admission lives outside.
    import ast
    def worker_ast(path):
        return [ast.dump(f,include_attributes=False) for f in ast.parse(path.read_text()).body
                if isinstance(f,ast.FunctionDef) and f.name in ('worker','run_one')]
    if worker_ast(D/'neural_pool_trial.py')!=worker_ast(Path(__file__).with_name('neural_pool_trial.py')):
        raise ValueError('worker changed')
    R.mkdir(mode=0o700,exist_ok=False)
    for name,pin in old['files'].items():
        if sha(D/name)!=pin:raise ValueError('donor drift')
        if name.startswith(('data-0/','data-1/','episode-')) or name in ('run.sbatch','bin/singularity'):continue
        dest=R/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dest)
    for name in (NAME,'width_contract.py','width_readout.py','live_identity.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    for index in range(37):(R/f'episode-{index}/work/input_cache').mkdir(parents=True)
    (R/'empty-data').mkdir(exist_ok=True);(R/'bin').mkdir(exist_ok=True)
    for block in range(9):(R/f'mutex-{block}').touch(exist_ok=False)
    (R/'bin/singularity').write_text(f'#!{n.PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom neural_width_trial import configure\nconfigure().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    (R/'run.sbatch').write_text(batch_script())
    inputs=dict(old['input_files'])
    for program in old['programs']:
        if not Path(program['data']).is_dir():raise ValueError('donor input missing')
    plan=dict(source_commit=commit,donor_plan_sha256=DONOR,schedule=schedule(),programs=old['programs'],
        gpus=1,total_cpu=6,physical_cpu=6,node='gpu27',allocation_seconds=CAP,gpu_hours_cap=1.5,
        planned_executions=36,source_seed=42,harness_seed=130701,task_image_sha256=n.IMAGE_SHA,
        candidate_timeout=450,worker_hard_seconds=550,interpreter_deadline_seconds=525,
        widths=WIDTHS,all_four_startup_parallel=True,common_all_ready_barrier=True,
        single_change='Fixed FIFO execution permits 1/2/4; same four pre-initialized programs, inputs, training settings and allocation. Permit reclaimed only after successful worker exit and close.',
        scope='Two copies per existing neural source, not four distinct programs/tasks/seeds. Three systems restarts, nine pool blocks, Latin-square arm order. No live agent or quality claims.',
        primary='All36 complete, original step count and numerical-output equivalence; report all per-repeat makespan ratios, first/mean/last returns, telemetry and full allocation cost. No predeclared winner.',
        next_decision='If share4 equals/beats share2 without correctness loss, simple wider concurrency remains strong baseline; do not claim need for semantic control. If share4 loses, only evidence of interference in this fixed load, not adaptive-policy superiority.',
        failure='No replacement, no restart or timeout extension. Stop new blocks after any failed execution/cleanup/identity/telemetry gate. Retain36 denominator.',
        no_api=True,no_base_training=True,no_quality_scores=True,no_protected_data=True,
        common_gateway='Bind the actual pinned _gateway_port interface to unique job/run ports in all arms; old worker unused-name assignment remains inert. Verify own-child announced ports after closure.',
        warmup_separate_and_in_cost=True,no_concurrent_own_heavy_preparation=True,
        input_files=inputs,files={str(p.relative_to(R)):sha(p) for p in R.rglob('*')
            if p.is_file() and not p.name.startswith('mutex-')})
    write(R/'plan.json',plan)
    p=configure();m=p.runtime()
    if sha(m.TASK_IMAGE)!=n.IMAGE_SHA:raise ValueError('image drift')
    if len(schedule())!=36 or not callable(getattr(sys.modules[__name__],'configure',None)):
        raise ValueError('wrapper interface')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    check()
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),gpu_executions=0,
        worker_AST_unchanged=True,source_and_inputs_verified=True,image_verified=True))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),assigned=36,gpu_hours_cap=1.5)))


def worker(index):
    configure().runtime()
    from dojo.core.interpreters.jupyter import jupyter_client as client
    from dojo.core.interpreters.jupyter import jupyter_interpreter as ji
    if sha(client.__file__)!=CLIENT_SHA or sha(Path(__file__).with_name('bounded_readiness.py'))!=HELPER_SHA:
        raise ValueError('handshake pin')
    if not hasattr(ji,'_gateway_port') or not 0<=index<=36:raise ValueError('pinned gateway interface')
    port=31000+(int(os.environ['SLURM_JOB_ID'])%400)*40+index
    ji._gateway_port=lambda:port
    write(R/f'episode-{index}/gateway-request.json',dict(port=port))
    client.JupyterKernelClient.wait_for_ready=lambda self,timeout_seconds=None:wait_for_ready(self,120 if timeout_seconds is None else timeout_seconds)
    return n.worker(index)


def controller():
    plan=check();p=configure();m=p.runtime();start=time.monotonic();error=None
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':
        raise ValueError('allocation identity')
    gpu=m.infra().native_uuids(1)[0];topology=cpu_topology()
    write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,
        affinity=sorted(os.sched_getaffinity(0)),cpu_topology=topology,start=time.time()))
    try:
        if len(cores(topology))!=6 or p.gpu_sample(gpu)['apps']:raise ValueError('resource gate')
        if not n.run_one(36)['complete'] or p.gpu_sample(gpu)['apps']:raise ValueError('warmup/release')
        for block in range(9):
            if time.monotonic()-start+560>CAP-100:raise TimeoutError('whole block budget')
            rows=schedule()[4*block:4*block+4]
            if p.gpu_sample(gpu)['apps']:raise ValueError('preblock release')
            samples=[];errors=[];stop=threading.Event()
            def observe():
                while not stop.is_set():
                    try:samples.append(p.gpu_sample(gpu))
                    except Exception as e:errors.append(type(e).__name__);break
                    stop.wait(.5)
            observer=threading.Thread(target=observe,daemon=True);begin=time.time();observer.start();outcomes=[]
            try:
                with cf.ThreadPoolExecutor(max_workers=4) as pool:
                    for future in cf.as_completed([pool.submit(n.run_one,r['index']) for r in rows]):
                        outcome=future.result();outcomes.append(outcome)
                        abort=R/f'abort-{block}.json'
                        if not outcome['complete'] and not abort.exists():write(abort,dict(failed_index=outcome['index']))
            finally:stop.set();observer.join(timeout=10)
            write(R/f'block-{block}.json',dict(block=block,arm=rows[0]['arm'],repeat=rows[0]['repeat'],
                start=begin,end=time.time(),outcomes=outcomes,telemetry_errors=errors))
            write(R/f'telemetry-{block}.json',samples)
            if errors or observer.is_alive() or p.gpu_sample(gpu)['apps']:raise ValueError('telemetry/release')
            if not all(o['complete'] for o in outcomes):raise ValueError('failed block; no replacement')
    except Exception as e:error=type(e).__name__
    finally:
        rows=[]
        for s in schedule():
            ep=R/f'episode-{s["index"]}';r=dict(**s,source_commit=plan['source_commit'],status='not_started')
            if (ep/'started.json').exists():r['status']='incomplete'
            if (ep/'closed.json').exists():r.update(read(ep/'closed.json'));r['status']='failed'
            if (ep/'completed.json').exists():
                d=read(ep/'completed.json');r.update({k:v for k,v in d.items() if k not in ('output','gpu_training')})
                r['status']='complete' if d['complete'] and r.get('returncode')==0 else 'failed'
                r['gpu_steps']=d.get('gpu_training',{}).get('steps');r['output_sha256']=d.get('output',{}).get('sha256')
            rows.append(r)
        write(R/'runs.json',rows)
        with (R/'runs.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
        write(R/'closed.json',dict(planned=36,attempted=sum(r['status']!='not_started' for r in rows),
            completed=sum(r['status']=='complete' for r in rows),controller_error=error,elapsed_seconds=time.monotonic()-start))
    return 1 if error else 0


def submit():
    check();env=configure().runtime().infra().clean_env()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_seconds_cap=CAP,assigned=36))
    r=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),
        '--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
    job=r.stdout.strip().split(';')[0]
    if r.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,assigned=36,gpu_hours_cap=1.5)))


if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('prepare','submit','controller','worker'))
    ap.add_argument('--commit');ap.add_argument('--index',type=int);a=ap.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':sys.exit(worker(a.index))
    else:sys.exit(globals()[a.mode]())
