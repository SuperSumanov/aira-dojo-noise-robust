"""Narrow14 same-source GPU capacity checks, not rescue of two-family gate."""
import ast
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from verify_six_gpu_capacity import sha

BASE=Path('/research/d7/spc/yzyang4')
DONOR=BASE/'resource-six-gpu-capacity-20261011-v2'
PIN='024b608742e3934a8e716bd4c867243cf1f76be9c4439e25f19b9e54930f2120'
ROOT=BASE/'resource-unet-six-capacity-20261011-v2'
DRIVER='six_gpu_capacity_20261011.py'


def schedule():
    rows=[dict(index=0,block=0,slot=0,program=1,width=1),dict(index=1,block=1,slot=0,program=1,width=1)]
    for b in (2,3):
        for s in range(6):rows.append(dict(index=len(rows),block=b,slot=s,program=1,width=6))
    return rows


def transform(source):
    tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='schedule')
    start=sum(map(len,source.splitlines(keepends=True)[:fn.lineno-1]));end=sum(map(len,source.splitlines(keepends=True)[:fn.end_lineno]))
    source=source[:start]+'def schedule():\n    return '+repr(schedule())+'\n'+source[end:]
    old="'resource-six-gpu-capacity-20261011-v2'";assert source.count(old)==1
    source=source.replace(old,repr(ROOT.name));assert source.count('CAP=4200')==1
    return source.replace('CAP=4200','CAP=2400')


def prepare():
    assert sha(DONOR/'plan.json')==PIN
    old=json.loads((DONOR/'plan.json').read_text());close=json.loads((DONOR/'allocation-closed.json').read_text())
    assert close['service_stopped']
    assert old['programs'][1]['source_sha256']=='c60e3f1cc3b4613a9707f1c86df12d6d45f1ef36a48ee858b768f9cc8806598d'
    qa=json.loads((BASE/'resource-cache-qualification-20261011-v1/qualification-audit.json').read_text())
    assert qa['gate'] and qa['rows'][1]['complete'] and qa['rows'][1]['gpu_steps']==588
    for n,h in old['files'].items():assert sha(DONOR/n)==h
    for n,h in old['input_files'].items():assert sha(n)==h
    ROOT.mkdir(mode=0o700)
    for n in old['files']:
        if n=='run.sbatch':continue
        out=ROOT/n;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,out)
    (ROOT/DRIVER).write_text(transform((DONOR/DRIVER).read_text()))
    shutil.copyfile(__file__,ROOT/Path(__file__).name)
    for r in schedule():(ROOT/f"episode-{r['index']}/input_cache").mkdir(parents=True)
    (ROOT/'service-cache/tmp').mkdir(parents=True)
    with (ROOT/'.service.env').open('x') as f:f.write('VLLM_API_KEY='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    batch=f'''#!/bin/bash
#SBATCH --job-name=unet-two-plus-six
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:8
#SBATCH --cpus-per-task=32
#SBATCH --hint=nomultithread
#SBATCH --time=00:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 2340s {BASE}/venvs/aira/bin/python -B {ROOT}/{DRIVER} allocation
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    p=dict(old);p.update(schedule=schedule(),planned=14,source_families=1,used_program_indices=[1],
        allocation_seconds_cap=2400,gpu_seconds_cap=19200,donor_plan_sha256=PIN,
        question='Can2 local model GPUs coexist with6 simultaneous replicas of one qualified real GPU training program?',
        qualification='Post-failure deliberately narrower UNet-only capacity diagnostic; not confirmation of two-family gate and not six tasks.',
        intervention='No algorithm/source/image/input/seed/450s timeout change. One source replicated; 1/1/6/6 blocks.',
        acceptance='14/14 candidate+requests;588 CUDA-gradient steps each;6 distinct task GPU UUIDs separate from2service GPUs;all91 same-source output pairs within1e-5;all-in cleanup/cost.',
        original_failures='17550 entry failure and17554 first CNN timeout remain failed and unreplaced; selected fast qualified source cannot establish general production capacity.',
        unsubmitted_v1='Preserved incomplete preparation: legacy batch outer timeout was4170s rather than assumed4140s. No plan, launch or GPU job. v2 emits explicit batch with same fixed new budget.',
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file() and f.name!='.service.env' and '__pycache__' not in f.parts})
    with (ROOT/'plan.json').open('x') as f:json.dump(p,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(prepared=True,plan_sha256=sha(ROOT/'plan.json'),planned=14,source_families=1,gpu_seconds_cap=19200)))


if __name__=='__main__':os.umask(0o077);prepare()
