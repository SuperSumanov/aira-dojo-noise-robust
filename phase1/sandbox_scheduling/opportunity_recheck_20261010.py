"""Post-selected same-program reexecution, not new independent search evidence.

All two native-accepted Improve nodes in closed exposure-v1, parents and children,
two original-seed restarts: eight executions, one3090 <=45min. No generator/API.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time
from decimal import Decimal
from lifecycle_pilot import read, write, sha, load

B=Path('/research/d7/spc/yzyang4')
D=B/'scheduling-live-exposure-20261009-v1'
R=B/'scheduling-opportunity-recheck-20261010-v1'
PY=B/'venvs/aira/bin/python'
NAME='opportunity_recheck_20261010.py'
DONOR='b78c0101dec77c6c919a9f7669a07e4c6a5f377a20437e301c0fb8025ab047aa'
DIAGNOSTIC='0733fb3b789e77f243a3bf64fe67ad5f43b8d3cf8b08de45ef2fe6d6a724844b'
RUNTIME='b422a17094a6971218731054b53b56888505150b82f5309990b0b629577da4c9'
CAP=2700


def schedule():
    return [dict(index=4*r+2*p+j,repeat=r,pair=p,role=role,program=2*p+(role=='child'))
            for r in range(2) for p in range(2)
            for j,role in enumerate(('parent','child') if r==0 else ('child','parent'))]


def runtime():
    if sha(R/'runtime.py')!=RUNTIME:raise ValueError('runtime drift')
    m=load('recheck_runtime',R/'runtime.py');m.R=R;m.setup();return m


def config_environment():
    # Parsing only: no client is constructed and no real credential is loaded.
    os.environ.update(PRIMARY_KEY='offline-fixture',PRIMARY_KEY_QWEN3_8_27B='offline-fixture',
        HARDWARE='one NVIDIA RTX3090, six CPU cores',TIME_LIMIT='50 minutes',
        TIME_LIMIT_SECS='3000',STEP_LIMIT='10000')


def check():
    plan=read(R/'plan.json')
    if plan['schedule']!=schedule() or plan['allocation_seconds']!=CAP:raise ValueError('plan')
    for path,pin in plan['files'].items():
        if sha(R/path)!=pin:raise ValueError('frozen file drift')
    for path,pin in plan['public_inputs'].items():
        if sha(path)!=pin:raise ValueError('input drift')
    return plan


def prepare(commit):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('exact source commit')
    if sha(D/'plan.json')!=DONOR or sha(D/'native-opportunity-diagnosis-v1.json')!=DIAGNOSTIC:
        raise ValueError('closed source identity')
    if not (D/'closed.json').exists():raise ValueError('not closed')
    old=read(D/'plan.json');prior=read(D/'native-opportunity-diagnosis-v1.json')
    if sha(D/'source/src/dojo/core/solvers/utils/response.py')!=prior['native_extractor_sha256']:
        raise ValueError('extractor drift')
    extractor=load('recheck_extractor',D/'source/src/dojo/core/solvers/utils/response.py').extract_code
    from exposure_native_opportunity import diagnose
    from live_readout import ground_scores,lines
    from throughput_pilot import code_safe
    pairs=[]
    for row in old['schedule']:
        ep=D/f'episode-{row["index"]}'
        nodes=[n for n in lines(ep/'checkpoint/journal.jsonl') if n.get('operators_used')]
        candidates=sorted([read(p) for p in ep.glob('candidate-*.json') if '.private.' not in p.name],key=lambda c:c['elapsed_seconds'])
        diagnostic=diagnose(nodes,candidates,1 if row['task']=='random-acts-of-pizza' else -1,extractor)
        expected=next(r for r in prior['rows'] if r['index']==row['index'])
        if diagnostic['counts']!=expected['counts']:raise ValueError('closed counts drift')
        if not ground_scores(read(ep/'finished.json'),candidates,[read(p)['receipt'] for p in ep.glob('scored-*.json')]):raise ValueError('external grounding')
        by_step={n['step']:(n,c) for n,c in zip(nodes,candidates)}
        for n,c in zip(nodes,candidates):
            if n['operators_used'][0]!='improve' or n['is_buggy'] or n['metric'] is None:continue
            if row['task']!='random-acts-of-pizza' or len(n['parents'])!=1:raise ValueError('declared two Pizza pairs')
            parent,pc=by_step[n['parents'][0]]
            if parent['is_buggy'] or not pc['valid']:raise ValueError('parent grounding')
            items=[]
            for role,node,candidate in [('parent',parent,pc),('child',n,c)]:
                code=extractor(node['code']);code_safe(code.encode())
                if not code or hashlib.sha256(code.encode()).hexdigest()!=candidate['code_sha256']:raise ValueError('source')
                items.append(dict(role=role,code=code,code_sha256=candidate['code_sha256'],original_score=candidate['score'],
                    original_exec_seconds=candidate['exec_seconds'],seed=row['seed'],task=row['task'],source_episode=row['index']))
            pairs.append(items)
    if len(pairs)!=2:raise ValueError('retain exactly all two accepted Improve pairs')
    R.mkdir(mode=0o700,exist_ok=False)
    for name,pin in old['files'].items():
        if not (name.startswith(('source/','forets_','opencl-vendors/')) or name=='runtime.py'):continue
        if sha(D/name)!=pin:raise ValueError('donor source drift')
        out=R/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,out)
    for name in (NAME,'lifecycle_pilot.py','bounded_readiness.py','live_identity.py','test_opportunity_recheck.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    (R/'programs').mkdir();(R/'configs').mkdir();(R/'bin').mkdir()
    programs=[]
    for pair in pairs:
        for item in pair:
            i=len(programs);code=item.pop('code');(R/f'programs/{i}.py').write_text(code)
            programs.append(item)
    for row in schedule():
        ep=R/f'episode-{row["index"]}';ep.mkdir();source=programs[row['program']]
        cfg=read(D/f'configs/{source["source_episode"]}.json')
        cfg['id']='r14-recheck-'+str(row['index'])
        cfg['metadata'].update(script_id='r14-recheck-20261010',base_path=str(R/'source'))
        cfg['logger'].update(output_dir=str(ep/'native-log'),write_env_vars=False,print_config=False,use_wandb=False,use_console=False)
        cfg['interpreter']['working_dir']=str(ep/'work')
        cfg['task'].update(results_output_dir=str(ep/'task-output'),cache_dir=str(R/'no-official-data'))
        write(R/f'configs/{row["index"]}.json',cfg)
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import runtime\nruntime().task_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-recheck
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --hint=nomultithread
#SBATCH --time=00:45:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 2660s srun --exclusive --ntasks=1 --cpus-per-task=6 --gres=gpu:1 --hint=nomultithread {PY} -B {R/NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    plan=dict(source_commit=commit,donor_plan_sha256=DONOR,diagnostic_sha256=DIAGNOSTIC,programs=programs,
        schedule=schedule(),allocation_seconds=CAP,gpu_hours_cap=.75,gpus=1,cpus=6,node='gpu27',
        candidate_timeout_seconds=240,worker_hard_seconds=320,source_seed_unchanged=True,
        task_image_sha256=old['task_image_sha256'],public_inputs=old['public_inputs'],
        question='Do both previously accepted Pizza parent/child differences survive two same-program original-seed restarts?',
        decision='All eight executions retained. Pairwise deltas for both restarts; missing remains missing. No extra retries/replacement, no seed sweep. Positive-pair repeatability only if both new deltas are positive and all outputs grounded.',
        limitation='Post-selected pairs on reused dev data, not independent new tasks/parents or scheduling effects. Fresh serial reexecution changes contention from original live pool; timed code may do different work. Not a clone of original search or a noise-free effect.',
        constraints=['original candidate bytes','original RNG prefix','original public view and external scorer','original image','240s candidate cap','one GPU/six CPUs for all','no generator or API','no protected/test reads','no old writer rerun','all failures charged','write-once fresh root'],
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()})
    write(R/'plan.json',plan);cpu()
    print(json.dumps(dict(status='PREPARED',plan_sha256=sha(R/'plan.json'),executions=8,gpu_hours_cap=.75,
        program_original_exec_seconds=[p['original_exec_seconds'] for p in programs])))


def cpu():
    plan=check();m=runtime();config_environment()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.utils.logger import config_logger
    if sha(m.TASK_IMAGE)!=plan['task_image_sha256']:raise ValueError('image drift')
    for row in schedule():
        cfg=RunConfig.load_from_json(R/f'configs/{row["index"]}.json');cfg.validate();config_logger(cfg)
        task=MLEBenchTask(cfg.task)
        if task.private_dir.exists() or task._search_only_score is None or cfg.interpreter.timeout!=240:raise ValueError('dev-only contract')
        if sha(cfg.task.search_only_dev_scorer_path)!=cfg.task.search_only_dev_scorer_sha256:raise ValueError('scorer drift')
        compile((R/f'programs/{row["program"]}.py').read_text(),'candidate.py','exec')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    subprocess.run([str(PY),'-B','-m','unittest','test_opportunity_recheck'],cwd=R,check=True)
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),configs=8,gpu_executions=0,model_calls=0,
        image_hash_verified=True,source_input_score_pins_verified=True,private_task_path_absent=True,
        source_contracts=plan['constraints']))


def worker(index):
    plan=check();m=runtime();config_environment();row=schedule()[index];program=plan['programs'][row['program']];ep=R/f'episode-{index}'
    own=m.infra().native_uuids(1)
    os.environ.update(DOJO_GPU_UUIDS=own[0],POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),
        PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=own))
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),
        host_boot_id=_host_boot_id(),gpu_uuids=own,container_pid=None,container_process_start_ticks=None))
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.logger import config_logger
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.core.tasks.constants import EXECUTION_OUTPUT,VALID_SOLUTION,VALIDATION_FITNESS,AUX_EVAL_INFO
    from dojo.core.interpreters.jupyter import jupyter_client as client
    from bounded_readiness import wait_for_ready
    client.JupyterKernelClient.wait_for_ready=lambda self,timeout_seconds=None:wait_for_ready(self,120 if timeout_seconds is None else timeout_seconds)
    task=None;state=None;error=None;result={};start=time.time();clean=False
    write(ep/'started.json',dict(**row,start=start))
    try:
        with ExperimentDeadline(300).activate():
            cfg=RunConfig.load_from_json(R/f'configs/{index}.json');config_logger(cfg)
            task=MLEBenchTask(cfg.task);interp=build(cfg.interpreter,INTERPRETER_MAP,data_dir=cfg.task.data_dir)
            state,_=task.prepare(solver_interpreter=interp,eval_interpreter=None)
            score=task._search_only_score
            def capture(name,submission):
                receipt=score(name,submission);shutil.copyfile(submission,ep/'prediction.private.csv')
                write(ep/'scorer-receipt.json',receipt);return receipt
            task._search_only_score=capture
            code=(R/f'programs/{row["program"]}.py').read_text()
            executable=f'import random as _r, numpy as _n\n_r.seed({program["seed"]})\n_n.random.seed({program["seed"]})\n'+code
            _,out=task.step_task(state,executable);execution=out[EXECUTION_OUTPUT]
            result=dict(valid=bool(out.get(VALID_SOLUTION)),score=out.get(VALIDATION_FITNESS),aux=out.get(AUX_EVAL_INFO),
                exit_code=execution.exit_code,timed_out=execution.timed_out,exec_seconds=execution.exec_time)
    except BaseException as exc:error=type(exc).__name__
    finally:
        if task is not None and state is not None:
            try:task.close(state);clean=True
            except BaseException as exc:error=error or type(exc).__name__
        write(ep/'finished.json',dict(**row,**result,complete=error is None and result.get('valid') is True and result.get('exit_code')==0 and not result.get('timed_out'),
            error_type=error,cleanup_attempted=clean,elapsed_seconds=time.time()-start,source_commit=plan['source_commit']))
    return 1 if error else 0


def terminate_owned(process,ep):
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    identity=read(ep/'identity.json') if (ep/'identity.json').exists() else {}
    pid=identity.get('container_pid');ticks=identity.get('container_process_start_ticks')
    def still_owned():
        try:
            return (identity.get('host_boot_id')==_host_boot_id() and pid and ticks
                and _process_start_ticks(pid)==ticks and os.getpgid(pid)==identity.get('container_pgid'))
        except ProcessLookupError:return False
    if still_owned():
        try:os.killpg(os.getpgid(pid),signal.SIGTERM)
        except ProcessLookupError:pass
        time.sleep(1)
        if still_owned():
            try:os.killpg(os.getpgid(pid),signal.SIGKILL)
            except ProcessLookupError:pass
    if process.poll() is None:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)


def controller():
    plan=check();m=runtime();start=time.monotonic();error=None
    if socket.gethostname().split('.')[0]!='gpu27':raise ValueError('node')
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID']:raise ValueError('allocation')
    from live_identity import cpu_topology,cores
    topology=cpu_topology()
    if len(cores(topology))!=6:raise ValueError('six physical CPUs')
    sys.path.insert(0,str(R/'source/src'))
    gpu=m.infra().native_uuids(1)[0]
    def apps():
        out=subprocess.check_output(['nvidia-smi','-i',gpu,'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True,timeout=10)
        return [v for v in out.splitlines() if v.strip()]
    write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,cpu_topology=topology))
    try:
        if apps():raise ValueError('preexisting GPU process')
        for row in schedule():
            if CAP-(time.monotonic()-start)<340:raise TimeoutError('full next execution budget unavailable')
            ep=R/f'episode-{row["index"]}'
            with (ep/'worker.private.log').open('xb') as log:
                proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(row['index'])],stdout=log,stderr=log,start_new_session=True)
                try:rc=proc.wait(timeout=320)
                except subprocess.TimeoutExpired:
                    terminate_owned(proc,ep);rc=124
            clean=not apps();write(ep/'closed.json',dict(returncode=rc,gpu_clean=clean))
            if not clean:raise ValueError('cleanup not verified; no expansion')
    except Exception as exc:error=type(exc).__name__
    finally:
        rows=[]
        for row in schedule():
            ep=R/f'episode-{row["index"]}';item=dict(**row,status='not_started',source_commit=plan['source_commit'])
            if (ep/'started.json').exists():item['status']='incomplete'
            if (ep/'finished.json').exists():item.update(read(ep/'finished.json'))
            if (ep/'closed.json').exists():
                item.update(read(ep/'closed.json'));item['status']='complete' if item.get('complete') and item['returncode']==0 and item['gpu_clean'] else 'failed'
            item.pop('aux',None);rows.append(item)
        write(R/'runs.json',rows)
        with (R/'runs.csv').open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=sorted({k for r in rows for k in r}));w.writeheader();w.writerows(rows)
        write(R/'closed.json',dict(planned=8,attempted=sum(r['status']!='not_started' for r in rows),complete=sum(r['status']=='complete' for r in rows),controller_error=error,elapsed_seconds=time.monotonic()-start))
    return 1 if error else 0


def summarize(rows,programs):
    expected=schedule()
    if len(rows)!=8 or len(programs)!=4:raise ValueError('fixed denominator')
    for row,s in zip(rows,expected):
        if any(row.get(k)!=v for k,v in s.items()):raise ValueError('schedule identity')
    pairs=[]
    for pair in range(2):
        deltas=[]
        for repeat in range(2):
            both={r['role']:r for r in rows if r['pair']==pair and r['repeat']==repeat}
            valid=all(r['status']=='complete' and r.get('grounded') is True
                and isinstance(r.get('score'),(int,float)) and not isinstance(r['score'],bool)
                and math.isfinite(r['score']) for r in both.values())
            deltas.append(str(Decimal(str(both['child']['score']))-Decimal(str(both['parent']['score']))) if valid else None)
        observed=[float(d) for d in deltas if d is not None]
        pairs.append(dict(pair=pair,original_delta=str(Decimal(str(programs[2*pair+1]['original_score']))-Decimal(str(programs[2*pair]['original_score']))),
            new_deltas=deltas,observed=len(observed),both_positive=all(d is not None and Decimal(d)>0 for d in deltas),
            median=None if len(observed)!=2 else statistics.median(observed),
            sample_std=None if len(observed)!=2 else statistics.stdev(observed)))
    return dict(planned=8,complete=sum(r['status']=='complete' for r in rows),pairs=pairs,
        all_grounded=all(r.get('grounded') is True for r in rows),
        boundary='Post-selected development programs, original-seed restarts; not new independent tasks/seeds, not a scheduling treatment comparison.')


def analyze():
    plan=check()
    if not (R/'closed.json').exists():raise ValueError('not closed')
    rows=read(R/'runs.json')
    for row in rows:
        ep=R/f'episode-{row["index"]}';row['grounded']=False
        if row['status']!='complete':continue
        result=read(ep/'finished.json');receipt=read(ep/'scorer-receipt.json');aux=result['aux']
        metric=aux['metric_name']
        if (receipt.get('submission_sha256')!=sha(ep/'prediction.private.csv')
                or aux['submission_sha256']!=receipt['submission_sha256']
                or receipt.get(metric)!=row['score']):raise ValueError('score/submission grounding')
        bindings=[read(p) for p in ep.glob('binding-*.json')]
        if not bindings or not all(b['namespace']['exact_device_namespace'] for b in bindings):raise ValueError('device isolation')
        row['grounded']=True
    result=summarize(rows,plan['programs'])
    result.update(plan_sha256=sha(R/'plan.json'),source_commit=plan['source_commit'],rows=rows)
    write(R/'readout-v1.json',result)
    print(json.dumps(dict(summary_sha256=sha(R/'readout-v1.json'),**result)))


def submit():
    check()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=20).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job; inspect rather than duplicate')
    write(R/'submit-intent.json',dict(plan_sha256=sha(R/'plan.json'),gpu_hours_cap=.75))
    p=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=25)
    job=p.stdout.strip().split(';')[0]
    if p.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; do not retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=.75)))


if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','worker','controller','analyze']);ap.add_argument('--commit');ap.add_argument('--index',type=int);a=ap.parse_args()
    if a.mode=='prepare':prepare(a.commit)
    elif a.mode=='worker':sys.exit(worker(a.index))
    else:sys.exit(globals()[a.mode]())
