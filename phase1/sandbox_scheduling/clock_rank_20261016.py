"""Conditional16: two chronological programs/task, same-task co-location.

Reuses the frozen18812 execution path; no changes to programs, seeds, input,
image,300s execution cap or task scoring. Not an E2E improvement experiment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
import clock_contention_20261016 as base

D=base.D
R=D.parent/'clock-rank-20261016-v1'
PY=base.PY
NAME=Path(__file__).name
CAP=5400
TASKS=base.TASKS
read,write,sha=base.read,base.write,base.sha

def schedule():
    return [dict(index=4*b+k,block=b,program=k,mode=mode,repeat=b//2,task=TASKS[k//2])
        for b,mode in enumerate(('solo','colocated','colocated','solo')) for k in range(4)]

def groups(block):
    indices=list(range(4*block,4*block+4))
    if block>=2:indices.reverse()
    return [[i] for i in indices] if block in (0,3) else [indices[:2],indices[2:]]

def configure():
    base.R=R;base.NAME=NAME;base.CAP=CAP;base.schedule=schedule
    base.gateway_port=lambda job,program:41000+(int(job)%1000)*2+program%2

def prior_gate():
    p=D.parent/'clock-contention-20261016-v2/readout-20261016-v1/summary.json'
    assert sha(p)=='b1b7053e5372b33770fa360a94aad393b911dfa9d96803ab9a5e0a0da32b5d40'
    s=read(p)
    assert s['structure'] and s['complete']==s['valid']==s['recomputed']==8
    assert len(s['overlaps'])==2 and all(x['host_training_envelope_overlap_seconds']>0 for x in s['overlaps'])
    assert any(x['complete'] and max(x['colocated_steps'])<=.9*min(x['solo_steps'])
        and -x['oriented_mean_score_delta']>max(x['solo_score_repeat_span'],x['colocated_score_repeat_span']) for x in s['effects'])
    return sha(p)

def select():
    from closed_clock_screen_20261016 import screen
    from dojo.utils.code_parsing import extract_code
    selected=[];plan=read(D/'plan.json')
    for task in TASKS:
        chosen=[];seen=set()
        for row in sorted(plan['schedule'],key=lambda r:r['index']):
            if row['task']!=task:continue
            ep=D/f"episode-{row['index']}"
            for p in sorted(ep.glob('candidate-*.json'),key=lambda p:int(p.name.split('-')[1].split('.')[0])):
                if '.private.' in p.name:continue
                c=read(p)
                if not(c['elapsed_seconds']<=1020 and c['valid'] is True and c['exit_code']==0 and not c['timed_out']):continue
                if c['code_sha256'] in seen:continue
                code=read(p.with_name(p.stem+'.private.json'))['code']
                assert hashlib.sha256(code.encode()).hexdigest()==c['code_sha256']
                structural=screen(code)
                if structural.get('credential_shape_hit'):raise ValueError('credential shape: stop without echo')
                if not structural.get('clock_exit_guards'):continue
                observed=[]
                for q in ep.glob('scored-*.json'):
                    if read(q)['receipt']['submission_sha256']==c['aux']['submission_sha256']:
                        training=ep/('gpu-training-'+q.stem.split('-')[1]+'.json')
                        if training.exists():observed.append(training)
                if len(observed)!=1 or read(observed[0]).get('cuda_gradient_steps',0)<=0:continue
                action=base.executable(code,row['seed'])
                h=hashlib.sha256(extract_code(action).encode()).hexdigest()
                assert h==c['aux']['executed_code_sha256'],'original executable drift'
                chosen.append(dict(task=task,source_episode=row['index'],source_candidate=int(p.stem.split('-')[1]),
                    seed=row['seed'],code_sha256=c['code_sha256'],executed_sha256=h,
                    original_config_sha256=sha(D/f"configs/{row['index']}.json"),
                    evidence_sha256=sha(p),gpu_observation_sha256=sha(observed[0]),action=action))
                seen.add(c['code_sha256'])
                if len(chosen)==2:break
            if len(chosen)==2:break
        assert len(chosen)==2,'insufficient chronological eligible programs: stop without replacements'
        selected.extend(chosen)
    return selected

def prepare(commit):
    configure();assert re.fullmatch('[a-f0-9]{40}',commit)
    prior=prior_gate();assert sha(D/'plan.json')==base.PIN
    old=read(D/'plan.json')
    for n,h in old['files'].items():assert sha(D/n)==h
    runtime=base.setup();chosen=select()
    R.mkdir(mode=0o700);(R/'configs').mkdir();(R/'bin').mkdir();(R/'programs').mkdir()
    for n in (NAME,'clock_contention_20261016.py','closed_clock_screen_20261016.py'):
        shutil.copyfile(Path(__file__).with_name(n),R/n)
    for k,p in enumerate(chosen):(R/f'programs/{k}.private.py').write_text(p.pop('action'))
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from unittest.mock import patch
    for row in schedule():
        ep=R/f"episode-{row['index']}";(ep/'work/input_cache').mkdir(parents=True)
        p=chosen[row['program']];cfg=read(D/f"configs/{p['source_episode']}.json")
        cfg=json.loads(json.dumps(cfg).replace(str(D/f"episode-{p['source_episode']}"),str(ep)))
        cfg['id']=f"clock-rank-{row['index']}";cfg['logger']['output_dir']=str(ep/'native-log')
        assert cfg['interpreter']['timeout']==300 and cfg['interpreter']['env']['PYTHONHASHSEED']==str(p['seed'])
        write(R/f"configs/{row['index']}.json",cfg)
        c=RunConfig.load_from_json(R/f"configs/{row['index']}.json");c.validate()
        assert not Path(c.task.private_dir).exists() and not c.logger.write_env_vars and not c.logger.use_wandb
        base.port_hook('100',row['program'])
        factory=build(c.interpreter,INTERPRETER_MAP,data_dir=c.task.data_dir);assert factory.factory
        with patch('dojo.core.interpreters.jupyter.jupyter_interpreter.SingularityJupyterServer') as server:
            assert factory.instance.port==base.gateway_port('100',row['program']) and factory.instance.timeout==300
            assert server.call_args.kwargs['port']==base.gateway_port('100',row['program'])
            factory.close()
    shim=f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom {Path(NAME).stem} import task_runtime\ntask_runtime()\n'
    (R/'bin/singularity').write_text(shim);os.chmod(R/'bin/singularity',0o700)
    (R/'run.sbatch').write_text(f'''#!/bin/bash
#SBATCH --job-name=r14-clock-rank
#SBATCH --partition=gpu_24h
#SBATCH --nodelist=gpu27
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --hint=nomultithread
#SBATCH --time=01:30:00
set -euo pipefail
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
exec srun --exclusive --ntasks=1 --cpus-per-task=4 --gres=gpu:1 {PY} -B {R/NAME} run
''')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not p.relative_to(R).parts[0].startswith('episode-')}
    write(R/'plan.json',dict(source_commit=commit,prior_summary_sha256=prior,donor_plan_sha256=base.PIN,
        donor_files=old['files'],files=files,schedule=schedule(),programs=chosen,
        task_image=str(runtime.TASK_IMAGE),task_image_sha256=old['task_image_sha256'],
        allocation_seconds=CAP,gpus=1,node='gpu27',worker_seconds=380,execution_seconds=300,
        selection='First2 distinct-source chronological valid CUDA/clock programs per task from18770; no score/rank sorting.',
        primary='Full16; same-task candidate order in solo/co per repeat, plus across-repeat interval separation. Rank change is mechanism, not E2E or significance.',
        stop='Any infrastructure/isolation/cleanup or first4 solo valid-CUDA failure stops remaining. No replacements or retries.'))
    print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),programs=chosen)))

def task_runtime():
    configure();base.setup()
    from pooling_trial_20261015 import namespace_command
    from forets_gpu_binding_20260911 import REAL_SINGULARITY
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    ep=Path(os.environ['POLICY9B_EPISODE']);assert ep.parent==R and re.fullmatch(r'episode-(?:[0-9]|1[0-5])',ep.name)
    n=read(R/'native.json');assert n['job']==os.environ['SLURM_JOB_ID'] and n['step']==os.environ['SLURM_STEP_ID']
    from resource_gpu_identity import gpu_uuids
    assert gpu_uuids(1)==n['gpu_uuids']
    cmd,env,receipt=namespace_command(args,n['gpu_uuids'][0])
    write(ep/f'binding-{os.getpid()}.json',dict(receipt,wall=time.time()))
    os.execve(REAL_SINGULARITY,cmd,env)

def run():
    configure();p=base.check();base.setup();start=time.monotonic();error=None;records=[]
    from resource_gpu_identity import gpu_uuids
    from live_identity import cpu_topology
    from live_search_trial_20261009 import owned_cleanup,gpu_sample,process_gone
    assert socket.gethostname().split('.')[0]==p['node']
    cpus={}
    for r in cpu_topology():cpus.setdefault((r['socket'],r['core']),[]).append(r['logical_cpu'])
    cores=sorted(min(v) for v in cpus.values());assert len(cores)==4
    own=gpu_uuids(1);assert not gpu_sample(own[0])['pids']
    write(R/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],
        gpu_uuids=own,cpu_slots=[cores[:2],cores[2:]]*2,wall=time.time()))
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
                ep=R/f'episode-{i}';owned_cleanup(proc,ep)
                identity=read(ep/'identity.json') if (ep/'identity.json').exists() else {}
                clean=bool(identity) and all(process_gone(identity.get(a),identity.get(b)) for a,b in
                    (('pid','process_start_ticks'),('container_pid','container_process_start_ticks')))
                records.append(dict(index=i,returncode=proc.poll(),cleanup=clean))
            for f in logs:f.close()
        assert all(x['returncode']==0 and x['cleanup'] for x in records)
        assert not gpu_sample(own[0])['pids']
    try:
        for b in range(4):
            for group in groups(b):execute(group)
            if b==0:
                assert all(read(R/f'episode-{i}/finished.json').get('valid')
                    and read(R/f'episode-{i}/gpu-training.json')['cuda_gradient_steps']>0 for i in range(4))
    except BaseException as exc:
        error=dict(type=type(exc).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(exc.__traceback__)])
    finally:write(R/'closed.json',dict(planned=16,records=records,error=error,elapsed_seconds=time.monotonic()-start,
        cleanup_verified=not gpu_sample(own[0])['pids']))
    return int(error is not None)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('action',choices=('inspect','prepare','submit','run','worker'))
    a.add_argument('--commit');a.add_argument('--index',type=int);v=a.parse_args();configure()
    if v.action=='inspect':
        prior_gate();base.setup();print(json.dumps([{k:v for k,v in p.items() if k!='action'} for p in select()]))
    elif v.action=='prepare':prepare(v.commit)
    elif v.action=='submit':base.submit()
    elif v.action=='worker':sys.exit(base.worker(v.index))
    else:sys.exit(run())
