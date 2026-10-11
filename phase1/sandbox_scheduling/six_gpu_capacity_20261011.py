"""Conditional, bounded 2 serving + 6 genuine GPU-program capacity validation.

Two public-data program families, not six tasks or new training seeds. No
quality labels/scores, no search policy, no causal speedup claim, no base fit.
"""
import concurrent.futures
import csv
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time

import service_thread_diag_20261011 as s
from resource_gpu_identity import gpu_uuids
from live_identity import cpu_topology, cores
from neural_instrument import INSTRUMENT, RECEIPT

ROOT=s.d.BASE/'resource-six-gpu-capacity-20261011-v1'
DONOR=s.d.BASE/'resource-service-diag-20261011-v3'
DONOR_SHA='3477f072efbd114bda046b9cb0a849b458f6fe9b8d7867773506cdff2fc2e41e'
FIXTURE=s.d.BASE/'scheduling-neural-extension-20261010-v1'
FIXTURE_SHA='bf0e2b24c267880ade8da3457ca5674b1a545c234485b3479ac0df41be2caa85'
NAME=Path(__file__).name
CAP=4200
s.ROOT=ROOT;s.NAME=NAME;s.d.ROOT=ROOT;s.d.NAME=NAME


def schedule():
    rows=[dict(index=0,block=0,slot=0,program=0,width=1),dict(index=1,block=1,slot=0,program=1,width=1)]
    for block in (2,3):
        for slot in range(6):
            rows.append(dict(index=len(rows),block=block,slot=slot,program=(slot+block)%2,width=6))
    return rows


def validate_block(service, service_cpu, workers, job):
    used_gpu=set(service['uuids']);used_cpu=cores(service_cpu);used_steps={service['step']}
    assert len(used_gpu)==2 and len(used_cpu)==8
    for ident in workers:
        gpu=set(ident['gpu_uuids']);cpu=cores(ident['cpu_topology'])
        assert ident['job']==job and ident['step'] not in used_steps
        assert len(gpu)==1 and len(cpu)==4 and not gpu&used_gpu and not cpu&used_cpu
        used_gpu|=gpu;used_cpu|=cpu;used_steps.add(ident['step'])
    return dict(gpu_count=len(used_gpu),physical_cores=len(used_cpu))


def output_structure(path, query):
    # Same structural contract as throughput_pilot.output_structure; no labels.
    with path.open(newline='') as f:
        reader=csv.reader(f);head=next(reader);rows=list(reader)
    with Path(query).open(newline='') as f:q=list(csv.reader(f))
    if len(rows)!=len(q)-1 or len(head)<2 or len(set(head))!=len(head):raise ValueError('output shape')
    if len({r[0] for r in rows})!=len(rows) or {r[0] for r in rows}!={r[0] for r in q[1:]}:raise ValueError('query identity mismatch')
    for row in rows:
        if len(row)!=len(head) or any(not math.isfinite(float(v)) for v in row[1:]):raise ValueError('nonfinite output')
    return dict(rows=len(rows),columns=len(head),sha256=s.d.sha(path))


def prepare():
    assert s.d.sha(DONOR/'plan.json')==DONOR_SHA and s.d.sha(FIXTURE/'plan.json')==FIXTURE_SHA
    prior=json.loads((DONOR/'closed.json').read_text())
    ended=json.loads((DONOR/'allocation-closed.json').read_text())
    assert prior['complete']==prior['requests_complete']==14
    assert ended['returncode']==0 and ended['service_stopped'] and ended['controller_stopped']
    old=json.loads((DONOR/'plan.json').read_text());fixture=json.loads((FIXTURE/'plan.json').read_text())
    assert fixture['query_public_train_only'] and fixture['no_official_test']
    for path,pin in fixture['input_files'].items():assert s.d.sha(path)==pin,'public fixture drift'
    ROOT.mkdir(mode=0o700)
    for name,pin in old['files'].items():
        if not(name.startswith('source/') or name in ('resource_diag_20261011.py','resource_pressure.py','service_thread_diag_20261011.py','service_entry.py')):continue
        assert s.d.sha(DONOR/name)==pin
        dest=ROOT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/name,dest)
    driver=ROOT/'service_thread_diag_20261011.py';source=driver.read_text()
    assert source.count("== 'gpu27'")==1
    driver.write_text(source.replace("== 'gpu27'","== 'gpu1'"))
    for name in (NAME,'resource_gpu_identity.py','live_identity.py','neural_instrument.py'):
        shutil.copyfile(Path(__file__).with_name(name),ROOT/name)
    (ROOT/'programs').mkdir()
    for index,program in enumerate(fixture['programs']):
        assert s.d.sha(FIXTURE/f'programs/{index}.py')==program['source_sha256']
        shutil.copyfile(FIXTURE/f'programs/{index}.py',ROOT/f'programs/{index}.py')
    for row in schedule():(ROOT/f"episode-{row['index']}").mkdir()
    (ROOT/'service-cache/tmp').mkdir(parents=True)
    with (ROOT/'.service.env').open('x') as f:f.write('VLLM_API_KEY='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    batch=f'''#!/bin/bash
#SBATCH --job-name=resource-two-plus-six
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:8
#SBATCH --cpus-per-task=32
#SBATCH --hint=nomultithread
#SBATCH --time=01:10:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=30s 4140s {s.d.PY} {ROOT}/{NAME} allocation
'''
    (ROOT/'run.sbatch').write_text(batch)
    subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    plan=dict(question='Can the fixed local model plus six real GPU training programs coexist without resource failures or leftover processes?',
        source_commit=s.d.SOURCE, fixture_plan_sha256=FIXTURE_SHA, prerequisite_plan_sha256=DONOR_SHA,
        programs=fixture['programs'],input_files=fixture['input_files'],schedule=schedule(),
        planned=14,serial_qualification=2,six_way_rounds=2,planned_requests=14,
        gpus=8,cpus=32,service_cpus=8,worker_cpus=4,service_gpus=2,execution_gpus=6,
        allocation_seconds_cap=CAP,gpu_seconds_cap=8*CAP,node='gpu1',
        startup_seconds=900,worker_seconds=650,candidate_seconds=450,
        source_seed=42,harness_seed=130701,libraries_threads=6,
        model_files=old['model_files'],service_image_sha256=old['service_image_sha256'],task_image_sha256=old['task_image_sha256'],
        service_model='qwen3.8-27b',reasoning_effort_requested='medium',max_tokens=512,
        request='One fixed program-context resource summary per candidate; transport/pressure only, not agent search.',
        sampler='1Hz host UID/cgroup; allocation supervisor is not a dedicated CPU-performance control.',
        intervention='Capacity acceptance only: no randomized performance or quality comparison.',
        stop='Any serial failure prevents six-way blocks; any block failure closes remainder; no replacements. Same per-candidate deadline.',
        acceptance='14/14 programs+requests,14 CUDA gradient receipts, separated service/task GPU UUIDs and physical CPU sets, output structure and repeated numerical consistency, full cost/cleanup.',
        numerical_check='Report exact output hash agreement and all per-source pairwise maximum absolute differences; fixed tolerance1e-5, not a quality guarantee. No score labels are read.',
        no_paid_api=True,no_base_training=True,no_quality_or_official_test=True,
        fixture_scope=fixture['fixture_scope'],not_new_tasks_or_independent_training_seeds=True,
        preflight=['exact source/image/model pins','all public fixture input hashes','no heldout target labels','real source parser argv isolated',
            'existing task image on same3090 family; actual CUDA identity/arithmetic before candidate','gpu1 physical32core placement check',
            'Slurm19 supported flags only','strict source/input/450s timeout unchanged','full8GPU all-in accounting',
            '14 complete denominator, first-failure gate','no retry/resample','service14-kernel prerequisite','bounded whole-job cleanup'],
        files={str(p.relative_to(ROOT)):s.d.sha(p) for p in ROOT.rglob('*') if p.is_file() and p.name!='.service.env' and '__pycache__' not in p.parts})
    s.d.write(ROOT/'plan.json',plan)
    print(json.dumps(dict(prepared=True,plan_sha256=s.d.sha(ROOT/'plan.json'),planned=14,gpu_seconds_cap=8*CAP)))


def worker(index):
    plan=json.loads((ROOT/'plan.json').read_text());row=plan['schedule'][index];program=plan['programs'][row['program']]
    ep=ROOT/f'episode-{index}';device=gpu_uuids(1)[0];topology=cpu_topology()
    assert len(cores(topology))==4
    s.d.configure();os.environ['CUDA_VISIBLE_DEVICES']=device
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as gateway
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    build=gateway._build_singularity_command
    def isolated(**kwargs):
        args=build(**kwargs);args[2:2]=['--no-mount','hostfs,bind-paths'];return args
    gateway._build_singularity_command=isolated
    server=executor=None;error=None;start=time.time()
    s.d.write(ep/'identity.json',dict(gpu_uuids=[device],cpu_topology=topology,job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID']))
    try:
        server=gateway.SingularityJupyterServer(working_dir=ep,superimage_directory=str(s.d.IMAGE.parent),
            superimage_version='2026-07-macos-v1',startup_timeout=90,
            read_only_binds={program['data']:'/workspace/workspace_input',str(ROOT/'resource_gpu_identity.py'):'/resource_gpu_identity.py'},
            env=dict(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='6',OPENBLAS_NUM_THREADS='6',MKL_NUM_THREADS='6',PYTHONHASHSEED='130701',CUDA_VISIBLE_DEVICES=device))
        executor=JupyterCodeExecutor(server,timeout=450)
        prelude="import sys,json,torch;sys.argv=['candidate.py'];sys.path.insert(0,'/');from resource_gpu_identity import gpu_uuids\n"
        prelude+=f"assert gpu_uuids(1)==[{device!r}]\n"
        prelude+="assert torch.cuda.is_available() and torch.cuda.device_count()==1\nx=torch.tensor([[1.,2.],[3.,4.]],device='cuda:0');assert (x@x).cpu().tolist()==[[7.,10.],[15.,22.]]\n"
        prelude+=INSTRUMENT
        result=executor.execute_code(prelude)
        assert result.exit_code==0 and not result.timed_out
        s.d.write(ep/'ready.json',dict(time=time.time(),cuda=True))
        deadline=time.monotonic()+150
        while not (ROOT/f"block-{row['block']}-go.json").exists():
            if time.monotonic()>deadline:raise TimeoutError('block barrier')
            time.sleep(.2)
        s.d.write(ep/'candidate-start.json',dict(time=time.time()))
        result=executor.execute_code((ROOT/f"programs/{row['program']}.py").read_text())
        s.d.write(ep/'execution.json',dict(exit_code=result.exit_code,timed_out=result.timed_out,seconds=result.exec_time))
        if result.exit_code or result.timed_out:
            text='\n'.join(map(str,result.term_out)).lower()
            s.d.write(ep/'errors.json',{x:x in text for x in ('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory','traceback')})
            raise RuntimeError('candidate execution')
        output=executor.fetch_file(Path('submission.csv'))
        with (ep/'output.private.csv').open('xb') as f:f.write(output)
        result=executor.execute_code(RECEIPT)
        assert result.exit_code==0 and not result.timed_out
        training=json.loads(executor.fetch_file(Path('gpu_training.json')))
        s.d.write(ep/'gpu-training.json',training)
        shape=output_structure(ep/'output.private.csv',Path(program['data'])/'test.csv')
        s.d.write(ep/'output-structure.json',dict(**shape,bytes=len(output),gpu_steps=training['steps']))
    except Exception as exc:error=type(exc).__name__
    finally:
        if executor is not None:
            try:executor.stop()
            except Exception as exc:error=error or type(exc).__name__
        if server is not None:server.stop()
        s.d.write(ep/'complete.json',dict(**row,complete=error is None,error_type=error,start=start,end=time.time()))
    return int(error is not None)


def one_request(row):
    start=time.time();result=dict(index=row['index'],complete=False)
    try:
        code=(ROOT/f"programs/{row['program']}.py").read_text()
        value=s.api('/v1/chat/completions',dict(model='qwen3.8-27b',messages=[dict(role='user',content='In at most five sentences, summarize the CPU, GPU, and process/thread usage of this program. Do not modify it.\n'+code)],
            reasoning_effort='medium',temperature=0,seed=49,max_tokens=512),timeout=120)
        result.update(complete=True,usage=value.get('usage'),finish_reason=value['choices'][0]['finish_reason'])
    except Exception as exc:result['error_type']=type(exc).__name__
    result.update(start=start,end=time.time());s.d.write(ROOT/f"request-{row['index']}.json",result);return result


def controller(end_time):
    planned=schedule();results=[];requests=[]
    service=json.loads((ROOT/'service-identity.json').read_text())
    service_cpu=json.loads((ROOT/'service-cpu.json').read_text())
    assert len(cores(service_cpu))==8
    for block in range(4):
        group=[r for r in planned if r['block']==block]
        if time.monotonic()+700>end_time:break
        processes=[];logs=[]
        try:
            for row in group:
                log=(ROOT/f"episode-{row['index']}/worker.private.log").open('x');logs.append(log)
                proc=subprocess.Popen(['srun','--exclusive','--ntasks=1','--gres=gpu:1','--cpus-per-task=4','--hint=nomultithread',str(s.d.PY),'-B',str(ROOT/NAME),'worker',str(row['index'])],stdout=log,stderr=log,start_new_session=True)
                processes.append((row,proc))
            deadline=time.monotonic()+140
            while not all((ROOT/f"episode-{r['index']}/ready.json").exists() for r in group):
                if any(p.poll() is not None for _,p in processes):raise RuntimeError('worker prelude failed')
                if time.monotonic()>deadline:raise TimeoutError('collective readiness')
                time.sleep(.5)
            identities=[json.loads((ROOT/f"episode-{row['index']}/identity.json").read_text()) for row in group]
            checked=validate_block(service,service_cpu,identities,os.environ['SLURM_JOB_ID'])
            s.d.write(ROOT/f'block-{block}-go.json',dict(time=time.time(),**checked))
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(group)) as pool:
                pending=[pool.submit(one_request,row) for row in group]
                for row,proc in processes:
                    rc=proc.wait(timeout=max(1,deadline+510-time.monotonic()))
                    results.append(dict(index=row['index'],returncode=rc))
                requests += [f.result() for f in pending]
            if any(x['returncode'] for x in results[-len(group):]) or any(not x['complete'] for x in requests[-len(group):]):break
        except Exception as exc:
            s.d.write(ROOT/f'block-{block}-failure.json',dict(error_type=type(exc).__name__))
            for row,proc in processes:
                if not any(x['index']==row['index'] for x in results):results.append(dict(index=row['index'],returncode=proc.poll()))
            break
        finally:
            for _,proc in processes:s.stop_owned(proc)
            for log in logs:log.close()
            time.sleep(3);s.d.write(ROOT/f'block-{block}-after.json',s.d.resource_pressure.snapshot())
    complete=sum((ROOT/f"episode-{r['index']}/complete.json").exists() and json.loads((ROOT/f"episode-{r['index']}/complete.json").read_text())['complete'] for r in planned)
    s.d.write(ROOT/'closed.json',dict(planned=14,attempted=len(results),complete=complete,rows=results,requests_complete=sum(x['complete'] for x in requests),requests_attempted=len(requests)))
    return int(complete!=14 or sum(x['complete'] for x in requests)!=14)


def service():
    top=cpu_topology();assert len(cores(top))==8
    s.d.write(ROOT/'service-cpu.json',top)
    return s.service()


def allocation():
    plan=json.loads((ROOT/'plan.json').read_text())
    for name,pin in plan['files'].items():assert s.d.sha(ROOT/name)==pin
    started=time.monotonic();end=threading.Event()
    def sample():
        with (ROOT/'pressure.jsonl').open('x') as f:
            while not end.is_set():f.write(json.dumps(s.d.resource_pressure.snapshot())+'\n');f.flush();end.wait(1)
    observer=threading.Thread(target=sample,daemon=True);observer.start()
    process=None;rc=1;error=None
    try:
        with (ROOT/'service.private.log').open('x') as log:
            process=subprocess.Popen(['srun','--exclusive','--ntasks=1','--gres=gpu:2','--cpus-per-task=8','--hint=nomultithread',str(s.d.PY),'-B',str(ROOT/NAME),'service'],stdout=log,stderr=log,start_new_session=True)
            deadline=time.monotonic()+900
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('service exited')
                try:healthy={v['id'] for v in s.api('/v1/models')['data']}=={'qwen3.8-27b'}
                except Exception:healthy=False
                if healthy:break
                time.sleep(2)
            else:raise TimeoutError('service startup')
            s.d.write(ROOT/'service-ready.json',s.d.resource_pressure.snapshot())
            rc=controller(started+CAP-60)
    except Exception as exc:error=type(exc).__name__
    finally:
        s.stop_owned(process);end.set();observer.join(timeout=10)
        s.d.write(ROOT/'allocation-after.json',s.d.resource_pressure.snapshot())
        s.d.write(ROOT/'allocation-closed.json',dict(returncode=rc,error_type=error,service_stopped=process is None or process.poll() is not None))
    return rc


if __name__=='__main__':
    os.umask(0o077);mode=sys.argv[1]
    if mode=='worker':sys.exit(worker(int(sys.argv[2])))
    if mode not in ('prepare','service','allocation'):raise ValueError('mode')
    sys.exit(globals()[mode]())
