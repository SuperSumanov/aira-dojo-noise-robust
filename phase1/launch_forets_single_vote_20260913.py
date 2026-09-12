"""Once-only route/dispatch for both frozen four-run blocks, no retry."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from forets_environment_build_20260912 import read,sha,write,encode

def checked(root):
    root=root.resolve(strict=True)
    if root.parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):raise ValueError('new package only')
    build=read(root/'build.json');prepared=read(root/'prepared.json',build['prepared_sha256'])
    from build_forets_single_vote_20260913 import order
    if [tuple((r['block'],r['task'],r['seed'],r['arm'])) for r in prepared['run_configs']]!=order():raise ValueError('matrix')
    check=read(root/'integration-check.json')
    if check['status']!='PASSED_CPU_INTEGRATION_NOT_GPU_ACCEPTANCE' or check['source_tree']!=build['source_tree']:raise ValueError('integration')
    sys.path[:0]=[str(root/'code'),str(root/'source/src')]
    from forets_native_run_20260911 import static_ready
    for block in (1,2):static_ready(root/'code',block)
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    return build,prepared

def route(root):
    checked(root)
    from forets_context_judge_20260912 import checked_catalog
    import requests
    response=requests.get('https://openrouter.ai/api/v1/models/qwen/qwen3-coder-plus/endpoints',timeout=(10,30),allow_redirects=False)
    response.raise_for_status();write(root/'block-1.plus-catalog.json',encode(checked_catalog(response.json())))
    for block in (1,2):
        p=subprocess.run([sys.executable,'-B',str(root/'code/forets_native_run_20260911.py'),'route','--block',str(block)],capture_output=True,text=True,timeout=350)
        write(root/f'route-{block}.private.log',(p.stdout+'\n'+p.stderr).encode())
        print(json.dumps(dict(block=block,rc=p.returncode,receipt=(root/f'block-{block}.route.json').exists())),flush=True)
        if p.returncode:raise RuntimeError('route failed; no GPU dispatch')

def submit(root):
    build,prepared=checked(root)
    from forets_stage_gate import validate_route_receipt
    from forets_paid_budget_20260911 import snapshot
    state=snapshot(root/'paid.sqlite')
    if state['stopped'] or state['unresolved']!=2:raise ValueError('billing')
    for block in (1,2):validate_route_receipt(root/f'block-{block}.route.json',root/'source')
    preflight=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_tree=build['source_tree'],controller_commit=build['commit'],
        prepared_sha256=build['prepared_sha256'],total_runs=8,total_gpu_hours_cap=3,blocks=2,gpus_per_block=1,cpus_per_block=6,
        typed_equal_arm_configs=4,search_seconds=600,program_seconds=300,rank_votes=1,
        query_duration_logged=True,original_image=True,protected_cohort_read=False,agent_training=False,
        prior_unknown_preserved=2,no_automatic_retry=True,readout_after_all_blocks=True,
        billing={k:v for k,v in state.items() if k!='scopes'},launchers={str(b):sha((root/f'launchers/singlevote-b{b}.sbatch').read_bytes()) for b in (1,2)})
    write(root/'preflight.json',encode(preflight))
    for block in (1,2):
        write(root/f'submit-intent-b{block}.json',encode(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),block=block,launcher_sha256=preflight['launchers'][str(block)])))
        p=subprocess.run(['sbatch','--parsable','--output='+str(root/f'slurm-b{block}-%j.out'),
            '--error='+str(root/f'slurm-b{block}-%j.err'),str(root/f'launchers/singlevote-b{block}.sbatch')],capture_output=True,text=True,timeout=25)
        write(root/f'submit-response-b{block}.private.log',(p.stdout+'\n'+p.stderr).encode())
        job=p.stdout.strip().split(';')[0]
        if p.returncode or not re.fullmatch('[0-9]+',job):raise RuntimeError('uncertain scheduler response; inspect before further action')
        record=dict(job=job,block=block,utc=dt.datetime.now(dt.timezone.utc).isoformat(),package=str(root),source_tree=build['source_tree'],controller_commit=build['commit'])
        write(root/f'launch-b{block}.json',encode(record));print(json.dumps(record),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('route','submit'));p.add_argument('root',type=Path)
    a=p.parse_args();os.umask(0o077);globals()[a.mode](a.root)
