"""Bounded capture of first missing info reply; no task/data/model/CUDA."""
import json,os,shutil,subprocess
from pathlib import Path
from verify_six_gpu_capacity import sha,read

BASE=Path('/research/d7/spc/yzyang4')
DONOR=BASE/'resource-kernel-protocol-20261011-v1'
PIN='dab97495194cf57248451b24c806113456a91dd5d6d5ddb62fafd20c924183ac'
ROOT=BASE/'resource-kernel-protocol-capture-20261011-v1'
DRIVER='kernel_protocol_trace_20261011.py'

def transform(source):
    replacements={"ROOT=d.BASE/'resource-kernel-protocol-20261011-v1'":f"ROOT=d.BASE/{ROOT.name!r}",
                  'WIDTH=6;ROUNDS=8;CAP=1800':'WIDTH=6;ROUNDS=32;CAP=1200',
                  "dict(planned=48,attempted=len(list(ROOT.glob('block-*-worker-*/host-before.json'))),":"dict(planned=192,attempted=len(list(ROOT.glob('block-*-worker-*/host-before.json'))),",
                  "if not all(v['gateway_counts_present'] for v in values):raise RuntimeError('observer missing')":
                  "if not all(v['gateway_counts_present'] for v in values):raise RuntimeError('observer missing')\n            if any(any(x['ready'] is False for x in v['calls']) for v in values):raise RuntimeError('captured readiness failure')"}
    for old,new in replacements.items():assert source.count(old)==1;source=source.replace(old,new)
    return source

def prepare():
    assert sha(DONOR/'plan.json')==PIN and read(DONOR/'closed.json')['complete']==48
    old=read(DONOR/'plan.json');assert all(sha(DONOR/n)==h for n,h in old['files'].items())
    ROOT.mkdir(mode=0o700)
    for n in old['files']:
        if n=='run.sbatch' or n.startswith('block-'):continue
        target=ROOT/n;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,target)
    (ROOT/DRIVER).write_text(transform((DONOR/DRIVER).read_text()))
    shutil.copyfile(__file__,ROOT/Path(__file__).name)
    counter=(DONOR/'gateway_counter_direct.py').read_text()
    for rep in range(32):
        for slot in range(6):
            ep=ROOT/f'block-{rep}-worker-{slot}';ep.mkdir();(ep/'gateway_counter.py').write_text(counter)
    batch=f'''#!/bin/bash
#SBATCH --job-name=kernel-reply-capture
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=6
#SBATCH --hint=nomultithread
#SBATCH --time=00:20:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 1160s srun --exclusive --ntasks=1 --gres=gpu:1 --cpus-per-task=6 --hint=nomultithread {BASE}/venvs/aira/bin/python -B {ROOT}/{DRIVER} controller
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    plan={k:old[k] for k in ('source_commit','task_image_sha256','seed')}
    plan.update(question='Capture first missing kernel-info reply with working enum-only gateway/client observers',
        donor_plan_sha256=PIN,planned=192,rounds=32,width=6,schedule=[dict(round=r,slot=s) for r in range(32) for s in range(6)],
        gpus=1,node='gpu3',physical_cpu_budget=6,gpu_seconds_cap=1200,
        stop='First observed readiness false, resource failure, crash, missing observer,210s round or20min job; no replacement or extension. Unstarted attempts retained.',
        no_task_data=True,no_model=True,no_cuda=True,no_paid_api=True,no_base_update=True,
        protocol='Same direct instrumented gateway and original single-query client as17556. No new retry, timeout or candidate execution.',
        boundary='Diagnostic until first event; not a reliability-rate estimate, causal fix, GPU capacity, throughput or quality result.',
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    with (ROOT/'plan.json').open('x') as f:json.dump(plan,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(prepared=True,plan_sha256=sha(ROOT/'plan.json'),planned=192,gpu_seconds_cap=1200)))

if __name__=='__main__':os.umask(0o077);prepare()
