"""Retain original Jupyter CLI; load enum observer in its exec child only.

Six hosts x eight rounds maximum, stop on first readiness failure. Diagnostic
import changes remain a possible timing confound; this is not a runtime fix.
"""
import json,os,shutil,subprocess
from pathlib import Path
from verify_six_gpu_capacity import sha,read

BASE=Path('/research/d7/spc/yzyang4')
DONOR=BASE/'resource-kernel-protocol-20261011-v1'
PIN='dab97495194cf57248451b24c806113456a91dd5d6d5ddb62fafd20c924183ac'
ROOT=BASE/'resource-kernel-cli-capture-20261011-v1'
DRIVER='kernel_protocol_trace_20261011.py'
SITE="""import os,sys
if os.path.basename(sys.argv[0])=='jupyter-kernelgateway':
    import gateway_counter
"""

def transform(source):
    old="    server._JUPYTER_BOOTSTRAP=\"import runpy;runpy.run_path('/workspace/gateway_counter.py',run_name='__main__')\""
    new="""    def observe_command(**kw):
        env=dict(kw['container_env'])
        assert 'PYTHONPATH' not in env
        env['PYTHONPATH']='/workspace/observer'
        return build(**dict(kw,container_env=env))
    server._build_singularity_command=observe_command"""
    replacements={"ROOT=d.BASE/'resource-kernel-protocol-20261011-v1'":f"ROOT=d.BASE/{ROOT.name!r}",
        'WIDTH=6;ROUNDS=8;CAP=1800':'WIDTH=6;ROUNDS=8;CAP=900',old:new,
        'finally:server._build_singularity_command=build':'finally:server._build_singularity_command=observe_command',
        "if not all(v['gateway_counts_present'] for v in values):raise RuntimeError('observer missing')":
        "if not all(v['gateway_counts_present'] for v in values):raise RuntimeError('observer missing')\n            if any(any(x['ready'] is False for x in v['calls']) for v in values):raise RuntimeError('captured readiness failure')"}
    for a,b in replacements.items():assert source.count(a)==1;source=source.replace(a,b)
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
    counter=(DONOR/'gateway_counter.py').read_text()
    assert "if __name__=='__main__':runpy.run_module('jupyter',run_name='__main__')" in counter
    for r in range(8):
        for s in range(6):
            ep=ROOT/f'block-{r}-worker-{s}'/'observer';ep.mkdir(parents=True)
            (ep/'gateway_counter.py').write_text(counter);(ep/'sitecustomize.py').write_text(SITE)
    batch=f'''#!/bin/bash
#SBATCH --job-name=kernel-cli-capture
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
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
timeout --signal=TERM --kill-after=15s 860s srun --exclusive --ntasks=1 --gres=gpu:1 --cpus-per-task=6 --hint=nomultithread {BASE}/venvs/aira/bin/python -B {ROOT}/{DRIVER} controller
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    plan={k:old[k] for k in ('source_commit','task_image_sha256','seed')}
    plan.update(question='Locate missing reply while preserving original Jupyter CLI exec path',donor_plan_sha256=PIN,
        planned=48,rounds=8,width=6,schedule=[dict(round=r,slot=s) for r in range(8) for s in range(6)],
        gpus=1,node='gpu3',physical_cpu_budget=6,gpu_seconds_cap=900,
        stop='First readiness false/resource failure/crash/missing observer;210s round;15min whole job;no replacement',
        no_task_data=True,no_model=True,no_cuda=True,no_paid_api=True,no_base_update=True,
        protocol='Original CLI/bootstrap and single-query client; sitecustomize imports existing enum observer only in jupyter-kernelgateway exec child, not in kernels.',
        boundary='Observer imports may perturb timing. Not a repair or causal before-after failure-rate, GPU capacity or quality estimate.',
        files={str(f.relative_to(ROOT)):sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    with (ROOT/'plan.json').open('x') as f:json.dump(plan,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(prepared=True,plan_sha256=sha(ROOT/'plan.json'),planned=48,gpu_seconds_cap=900)))

if __name__=='__main__':os.umask(0o077);prepare()
