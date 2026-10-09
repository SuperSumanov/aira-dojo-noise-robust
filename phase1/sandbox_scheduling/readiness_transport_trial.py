"""Fixed48 empty-kernel transport observations; <=1x3090x15min all-in.

This is a diagnosis, not a retry of17308 or a qualification override. No task
program, dataset, score, model service, base training or paid API is used.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import inspect
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

import lifecycle_pilot as life
from lifecycle_pilot import read,write,sha
from bounded_readiness import wait_for_ready
from live_identity import cpu_topology,cores

B=Path('/research/d7/spc/yzyang4')
R=B/'scheduling-readiness-transport-20261009-v1'
D=B/'scheduling-neural-width-20261009-v1'
PY=B/'venvs/aira/bin/python'
NAME='readiness_transport_trial.py'
DONOR='783934f461321858efbca68c9b70505323729ba921f6c9aba002ff4c42f38c5c'
CLIENT='a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'
HELPER='0fd8ead4c8eac2fc128b36d096ed15ceebeabc43a5fc5841d8c17e882ca381cd'
IMAGE='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda'


def schedule():
    rows=[]
    for repeat in range(6):
        for arm in (('serial','parallel4') if repeat%2==0 else ('parallel4','serial')):
            block=len(rows)//4
            for position in range(4):
                rows.append(dict(index=len(rows),block=block,repeat=repeat,arm=arm,position=position))
    return rows


def runtime():
    life.R=R
    module=life.runtime()
    source=inspect.getsource(module.task_runtime)
    if source.count("episode-[0-7]")!=1:raise ValueError('pinned native interface')
    source=source.replace("episode-[0-7]","episode-(?:[0-9]|[1-3][0-9]|4[0-7])")
    exec(compile(source,'bounded48-native-runtime','exec'),module.__dict__)
    return module


def check():
    plan=read(R/'plan.json')
    if plan['schedule']!=schedule() or plan['allocation_seconds']!=900:raise ValueError('matrix drift')
    for name,pin in plan['files'].items():
        if sha(R/name)!=pin:raise ValueError('source drift')
    return plan


class Observer:
    """Transparent info-only helper proxy; never sends an execution/restart."""
    def __init__(self,client):
        self.client=client;self.sent=set();self.counts=Counter();self.first_reply_seconds=None;self.begin=time.monotonic()
    def _send_message(self,**kw):
        if kw!=dict(content={},channel='shell',message_type='kernel_info_request'):raise ValueError('info-only')
        identity=self.client._send_message(**kw);self.sent.add(identity);self.counts['sent_info']+=1
        return identity
    def _receive_message(self,timeout_seconds):
        message=self.client._receive_message(timeout_seconds)
        if message is None:self.counts['receive_empty']+=1;return message
        self.counts['received']+=1
        if isinstance(message,dict):
            header=message.get('header');parent=message.get('parent_header')
            kind=message.get('msg_type') or (header.get('msg_type') if isinstance(header,dict) else None)
            # Enumerated classes only; no unknown raw strings/content are saved.
            known=kind if kind in ('kernel_info_reply','status','stream','error','execute_reply','execute_result') else 'other'
            self.counts['received_'+known]+=1
            matched=isinstance(parent,dict) and isinstance(parent.get('msg_id'),str) and parent['msg_id'] in self.sent
            if matched:self.counts['matched_parent']+=1
            if matched and kind=='kernel_info_reply':
                self.counts['matched_info_reply']+=1
                if self.first_reply_seconds is None:self.first_reply_seconds=time.monotonic()-self.begin
        return message
    def state(self):
        app=getattr(self.client,'_ws_app',None);sock=getattr(app,'sock',None)
        thread=getattr(self.client,'_thread',None)
        return dict(counts=dict(self.counts),first_reply_seconds=self.first_reply_seconds,
                    websocket_thread_alive=bool(thread and thread.is_alive()),
                    websocket_socket_connected=bool(sock and getattr(sock,'connected',False)))


def worker(index):
    module=runtime();row=schedule()[index];ep=R/f'episode-{index}'
    gpu=module.infra().native_uuids(1)[0]
    os.environ.update(DOJO_GPU_UUIDS=gpu,POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.core.interpreters.jupyter import jupyter_client as client
    from dojo.core.interpreters.jupyter import jupyter_interpreter as ji
    if sha(client.__file__)!=CLIENT or sha(R/'bounded_readiness.py')!=HELPER:raise ValueError('client pin')
    ji._gateway_port=lambda:31000+(int(os.environ['SLURM_JOB_ID'])%400)*60+index
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=[gpu],cpu_topology=cpu_topology()))
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=[gpu],container_pid=None,container_process_start_ticks=None))
    calls=[]
    def observed(self,timeout_seconds=None):
        observer=Observer(self);start=time.monotonic();ok=None;error=None
        try:
            ok=wait_for_ready(observer,120 if timeout_seconds is None else timeout_seconds)
            return ok
        except Exception as exc:error=type(exc).__name__;raise
        finally:calls.append(dict(ready=ok,seconds=time.monotonic()-start,error_type=error,**observer.state()))
    client.JupyterKernelClient.wait_for_ready=observed
    config=JupyterInterpreterConfig(working_dir=str(ep/'work'),timeout=10,container_runtime='singularity',
        superimage_directory=str(module.TASK_IMAGE.parent),superimage_version='2026-07-macos-v1',
        env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'6','PYTHONHASHSEED':'130901'})
    interp=None;error=None;cleanup=False;result=None;start=time.time()
    try:
        with ExperimentDeadline(155).activate():
            interp=build(config,INTERPRETER_MAP,data_dir=R/'empty-data')
            out=interp.run('pass')
            result=dict(exit_code=out.exit_code,timed_out=out.timed_out,exec_seconds=out.exec_time)
    except Exception as exc:error=type(exc).__name__
    finally:
        if interp is not None:
            try:interp.close();cleanup=True
            except Exception as exc:error=error or type(exc).__name__
        write(ep/'observed.json',dict(**row,start=start,end=time.time(),calls=calls,error_type=error,cleanup=cleanup,result=result,
            task_executions=0,gpu_compute_in_empty_cell=False))
    return 0 if cleanup and error is None else 1


def terminate_owned(process,ep):
    from dojo.main_local_worker import _process_start_ticks
    if (ep/'identity.json').exists():
        identity=read(ep/'identity.json');pid=identity.get('container_pid');ticks=identity.get('container_process_start_ticks')
        if pid and ticks and _process_start_ticks(pid)==ticks and os.getpgid(pid)==identity.get('container_pgid'):
            os.killpg(os.getpgid(pid),signal.SIGTERM);time.sleep(1)
            if _process_start_ticks(pid)==ticks:os.killpg(os.getpgid(pid),signal.SIGKILL)
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)


def run_one(index):
    ep=R/f'episode-{index}'
    with (ep/'worker.private.log').open('xb') as log:
        process=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(index)],stdout=log,stderr=log,start_new_session=True)
        try:code=process.wait(timeout=175)
        except subprocess.TimeoutExpired:terminate_owned(process,ep);code=124
    write(ep/'closed.json',dict(returncode=code))
    return code


def controller():
    check();module=runtime();begin=time.monotonic();error=None;attempted=[]
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':raise ValueError('job identity')
    if len(cores(cpu_topology()))!=6:raise ValueError('physical CPU count')
    gpu=module.infra().native_uuids(1)[0]
    write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,cpu_topology=cpu_topology()))
    try:
        for block in range(12):
            rows=schedule()[block*4:block*4+4]
            if time.monotonic()-begin>650:raise TimeoutError('budget reserve; no extension')
            if life.applications(gpu):raise ValueError('unexpected GPU client')
            if rows[0]['arm']=='parallel4':
                attempted.extend(r['index'] for r in rows)
                with ThreadPoolExecutor(max_workers=4) as pool:codes=list(pool.map(run_one,[r['index'] for r in rows]))
            else:
                codes=[]
                for row in rows:
                    if time.monotonic()-begin>650:raise TimeoutError('budget reserve; no extension')
                    attempted.append(row['index']);codes.append(run_one(row['index']))
                    if codes[-1]:raise RuntimeError('worker cleanup/structure failure')
            if any(codes) or life.applications(gpu):raise RuntimeError('worker cleanup/structure failure')
            # A false ready response is retained and does not stop diagnosis.
    except Exception as exc:error=type(exc).__name__
    finally:
        rows=[]
        for row in schedule():
            ep=R/f'episode-{row["index"]}'
            observed=read(ep/'observed.json') if (ep/'observed.json').exists() else None
            rows.append(dict(**row,attempted=row['index'] in attempted,observation=observed,
                returncode=read(ep/'closed.json')['returncode'] if (ep/'closed.json').exists() else None))
        write(R/'rows.json',rows)
        write(R/'closed.json',dict(planned=48,attempted=len(attempted),observed=sum(r['observation'] is not None for r in rows),controller_error=error,elapsed_seconds=time.monotonic()-begin))
    return 0 if error is None else 1


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit) or sha(D/'plan.json')!=DONOR:raise ValueError('exact source')
    donor=read(D/'plan.json');R.mkdir(mode=0o700,exist_ok=False)
    for name,pin in donor['files'].items():
        if not (name.startswith(('source/','forets_','opencl-vendors/')) or name=='runtime.py'):continue
        if sha(D/name)!=pin:raise ValueError('donor source drift')
        target=R/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,target)
    for name in (NAME,'bounded_readiness.py','lifecycle_pilot.py','live_identity.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    for row in schedule():(R/f'episode-{row["index"]}/work').mkdir(parents=True)
    (R/'empty-data').mkdir();(R/'bin').mkdir()
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom readiness_transport_trial import runtime\nruntime().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-transport-only
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --hint=nomultithread
#SBATCH --time=00:15:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 865s srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --hint=nomultithread {PY} -B {R/NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    write(R/'plan.json',dict(source_commit=commit,schedule=schedule(),allocation_seconds=900,gpus=1,physical_cpu=6,gpu_hours_cap=.25,
        donor_plan_sha256=DONOR,client_sha256=CLIENT,helper_sha256=HELPER,image_sha256=IMAGE,
        question='Does startup concurrency produce an observable kernel-info transport failure? No candidate retrial or effect gate override.',
        no_data=True,no_model=True,no_api=True,no_base_training=True,cell='pass',task_executions=0,
        decision='All48 remain. False readiness retained; no retry/restart. Stop only on cleanup/identity/budget failure. Absence of failure is not proof fixed. No automatic follow-up.',
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()}))
    module=runtime()
    if sha(module.TASK_IMAGE)!=IMAGE:raise ValueError('image drift')
    check();subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    from dojo.core.interpreters.jupyter import jupyter_client as client
    from dojo.core.interpreters.jupyter import jupyter_interpreter as ji
    if sha(client.__file__)!=CLIENT or not hasattr(ji,'_gateway_port'):raise ValueError('actual interface')
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),actual_client_pin_verified=True,actual_gateway_interface=True,
        no_gpu_execution=True,no_dataset=True,training_split_checkpoint_power_items_not_applicable=True))
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),planned=48,gpu_hours_cap=.25)))


def submit():
    check()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight identity')
    env=runtime().infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_seconds_cap=900))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=.25)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','submit','controller','worker']);parser.add_argument('--commit');parser.add_argument('--index',type=int)
    args=parser.parse_args()
    if args.mode=='prepare':prepare(args.commit)
    elif args.mode=='submit':submit()
    elif args.mode=='controller':sys.exit(controller())
    else:
        if args.index not in range(48):raise ValueError('explicit bounded index')
        sys.exit(worker(args.index))
