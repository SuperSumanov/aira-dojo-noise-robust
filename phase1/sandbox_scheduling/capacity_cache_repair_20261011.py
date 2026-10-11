"""Restore the fixture's existing private-cache contract, not a program edit.

Original 17550 remains closed. A bounded 1-GPU/two-program qualification must
pass before a fresh 2+6 capacity allocation can be prepared. No retries.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import time

BASE=Path('/research/d7/spc/yzyang4')
DONOR=BASE/'resource-six-gpu-capacity-20261011-v1'
PIN='a2ae3c0ad57ecd7822f140e8c2adc7ab09fc21033500eb971da0c94983b77243'
QUAL=BASE/'resource-cache-qualification-20261011-v1'
CAPACITY=BASE/'resource-six-gpu-capacity-20261011-v2'
PY=BASE/'venvs/aira/bin/python'
NAME=Path(__file__).name
DRIVER='six_gpu_capacity_20261011.py'
sys.path.insert(0,str(Path(__file__).parent))
from verify_six_gpu_capacity import sha, output


def read(p):return json.loads(p.read_text())
def write(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False)


def patched_driver(source, root_name):
    assert source.count("'resource-six-gpu-capacity-20261011-v1'")==1
    source=source.replace("'resource-six-gpu-capacity-20261011-v1'",repr(root_name))
    before="        if result.exit_code or result.timed_out:\n            text="
    after="        if result.exit_code or result.timed_out:\n            (ep/'execution.private.txt').write_text('\\n'.join(map(str,result.term_out)))\n            text="
    assert source.count(before)==1
    return source.replace(before,after)


def cache_preflight(root,p):
    data=Path(p['programs'][0]['data'])
    assert (data/'workspace_cache').is_symlink() and str((data/'workspace_cache').readlink())=='/workspace/input_cache'
    command="""import os,json
try:
 os.makedirs('/workspace/workspace_input/workspace_cache',exist_ok=True)
 print(json.dumps({'cache_path_ok':True}))
except Exception as e:print(json.dumps({'cache_path_ok':False,'error_type':type(e).__name__}))
"""
    rows=[]
    for mode in ('broken','fixed'):
        work=root/f'cache-preflight-{mode}';work.mkdir()
        if mode=='fixed':(work/'input_cache').mkdir()
        args=['singularity','exec','--containall','--cleanenv','--no-home','--no-mount','hostfs,bind-paths',
            '--bind',str(work)+':/workspace:rw','--bind',str(data)+':/workspace/workspace_input:ro',
            str(BASE/'aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif'),'python','-c',command]
        env={k:v for k,v in os.environ.items() if not k.startswith(('SINGULARITY','APPTAINER','CUDA','SLURM'))}
        result=subprocess.run(args,capture_output=True,text=True,timeout=60,env=env)
        assert result.returncode==0
        values=[json.loads(x) for x in result.stdout.splitlines() if x.startswith('{')]
        assert len(values)==1; rows.append(dict(mode=mode,**values[0]))
    assert rows[0]==dict(mode='broken',cache_path_ok=False,error_type='FileExistsError')
    assert rows[1]==dict(mode='fixed',cache_path_ok=True)
    write(root/'cache-preflight.json',dict(rows=rows,actual_task_image=True,gpu_execution=False,training=False))


def prepare(mode):
    assert mode in ('qualification','capacity') and sha(DONOR/'plan.json')==PIN
    old=read(DONOR/'plan.json'); assert read(DONOR/'allocation-closed.json')['service_stopped']
    root=QUAL if mode=='qualification' else CAPACITY
    if mode=='capacity':
        qa=read(QUAL/'qualification-audit.json'); assert qa['gate'] and qa['complete']==2
        assert qa['plan_sha256']==sha(QUAL/'plan.json') and qa['job']!= '17550'
    for name,pin in old['files'].items():assert sha(DONOR/name)==pin
    for name,pin in old['input_files'].items():assert sha(name)==pin
    root.mkdir(mode=0o700)
    for name in old['files']:
        if name=='run.sbatch':continue
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/name,target)
    (root/DRIVER).write_text(patched_driver((DONOR/DRIVER).read_text(),root.name))
    shutil.copyfile(__file__,root/NAME)
    shutil.copyfile(Path(__file__).with_name('verify_six_gpu_capacity.py'),root/'verify_six_gpu_capacity.py')
    rows=old['schedule'][:2] if mode=='qualification' else old['schedule']
    for r in rows:(root/f"episode-{r['index']}/input_cache").mkdir(parents=True)
    cache_preflight(root,old)
    gpu,cpus,cap=(1,4,1200) if mode=='qualification' else (8,32,4200)
    if mode=='capacity':
        (root/'service-cache/tmp').mkdir(parents=True)
        with (root/'.service.env').open('x') as f:f.write('VLLM_API_KEY='+secrets.token_hex(32)+'\n')
        os.chmod(root/'.service.env',0o600)
    runner=f'{NAME} allocation' if mode=='qualification' else f'{DRIVER} allocation'
    batch=f'''#!/bin/bash
#SBATCH --job-name=resource-cache-{mode}
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:{gpu}
#SBATCH --cpus-per-task={cpus}
#SBATCH --hint=nomultithread
#SBATCH --time={cap//3600:02}:{cap%3600//60:02}:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s {cap-30}s {PY} {root}/{runner}
'''
    (root/'run.sbatch').write_text(batch)
    subprocess.run(['bash','-n',str(root/'run.sbatch')],check=True)
    p=dict(old)
    p.update(donor_plan_sha256=PIN,qualification=mode=='qualification',schedule=rows,planned=len(rows),
        question='Requalify the two unchanged programs with their original private cache contract.' if mode=='qualification' else old['question'],
        cache_contract='Empty private /workspace/input_cache per episode, restoring the exact fixture contract; no shared cache/precompute.',
        entry_fix='Create previously omitted private directory. Retain remote-private exception output. No source/input/image/seed/450s timeout changes.',
        gpu_seconds_cap=gpu*cap,allocation_seconds_cap=cap,gpus=gpu,cpus=cpus,
        service_gpus=0 if mode=='qualification' else 2,execution_gpus=1 if mode=='qualification' else 6,
        planned_requests=0 if mode=='qualification' else 14,
        acceptance='Both original programs complete with CUDA gradients and correct public-query output structure; no performance inference.' if mode=='qualification' else old['acceptance'],
        prerequisite_cache_qualification=read(QUAL/'qualification-audit.json') if mode=='capacity' else None,
        files={str(x.relative_to(root)):sha(x) for x in root.rglob('*') if x.is_file() and x.name!='.service.env' and '__pycache__' not in x.parts})
    write(root/'plan.json',p)
    print(json.dumps(dict(root=str(root),plan_sha256=sha(root/'plan.json'),planned=len(rows),gpu_seconds_cap=gpu*cap,mode=mode)))


def allocation():
    root=QUAL;p=read(root/'plan.json');start=time.monotonic();records=[]
    for name,pin in p['files'].items():assert sha(root/name)==pin
    for r in p['schedule']:
        if time.monotonic()-start>p['allocation_seconds_cap']-680:break
        ep=root/f"episode-{r['index']}";proc=None;error=None
        try:
            with (ep/'worker.private.log').open('x') as log:
                proc=subprocess.Popen(['srun','--exclusive','--ntasks=1','--gres=gpu:1','--cpus-per-task=4','--hint=nomultithread',str(PY),'-B',str(root/DRIVER),'worker',str(r['index'])],stdout=log,stderr=log,start_new_session=True)
                deadline=time.monotonic()+140
                while not (ep/'ready.json').exists():
                    if proc.poll() is not None:raise RuntimeError('worker prelude')
                    if time.monotonic()>deadline:raise TimeoutError('worker readiness')
                    time.sleep(.5)
                ident=read(ep/'identity.json')
                assert len(set(ident['gpu_uuids']))==1 and ident['job']==os.environ['SLURM_JOB_ID']
                write(root/f"block-{r['block']}-go.json",dict(time=time.time(),qualification_only=True))
                rc=proc.wait(timeout=max(1,deadline+510-time.monotonic()))
                records.append(dict(index=r['index'],returncode=rc))
                if rc:break
        except Exception as exc:
            error=type(exc).__name__;records.append(dict(index=r['index'],returncode=proc.poll() if proc else None,error_type=error));break
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=8)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
    complete=sum((root/f"episode-{r['index']}/complete.json").exists() and read(root/f"episode-{r['index']}/complete.json")['complete'] for r in p['schedule'])
    write(root/'closed.json',dict(planned=2,attempted=len(records),complete=complete,rows=records))
    return int(complete!=2)


if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare(sys.argv[2])
    elif sys.argv[1]=='allocation':sys.exit(allocation())
    else:raise ValueError('mode')
