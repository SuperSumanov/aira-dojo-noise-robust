"""Freeze and dispatch the planned matrix once; all dynamic results remain sealed."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from forets_environment_build_20260912 import read,write,encode,sha


def checked(root):
    if root.resolve().parent!=Path('/research/d7/spc/yzyang4') or not root.name.startswith('forets-wallclock-20260912-'):
        raise ValueError('fresh e2e package only')
    build=read(root/'build.json');p=read(root/'prepared.json',build['prepared_sha256'])
    if p['run_count']!=16 or build['runs']!=16:raise ValueError('exact matrix')
    for name,status in [('integration-check.json','PASSED_CPU_INTEGRATION_NOT_GPU_ACCEPTANCE'),
        ('edit-scope-integration.json','PASSED_ACTUAL_OPERATOR_AND_SHARED_START_CPU')]:
        value=read(root/name)
        if value['status']!=status or value['source_tree']!=build['source_tree']:raise ValueError(name)
    local=read(root/'edit-scope-integration.json')
    if local['actual_operator_calls']!=48 or local['config_pairs']!=8 or not local['only_interface_differs']:
        raise ValueError('actual integration incomplete')
    action=read(root/'action-integration.json');batch=read(root/'edit-scope-batch-integration.json')
    if action['source_tree']!=build['source_tree'] or not action['independent_reader_matches']:raise ValueError('delivery integration')
    if batch['source_tree']!=build['source_tree'] or len(batch['rows'])!=2:raise ValueError('batch integration')
    for row in batch['rows']:
        if row['counts']!=dict(generation=2,ranking=0,execution=3,reservation=0,settlement=0) or row['actual_siblings']!=2:
            raise ValueError('native branch execution')
    original=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-103zf3nb/source/src/dojo/core/interpreters/jupyter')
    current=root/'source/src/dojo/core/interpreters/jupyter'
    for f in ('jupyter_client.py','jupyter_code_executor.py','kernel_readiness.py','gateway_wire.py','singularity_jupyter_server.py'):
        if sha((current/f).read_bytes())!=sha((original/f).read_bytes()):raise ValueError('original interpreter changed')
    sys.path[:0]=[str(root/'code'),str(root/'source/src')]
    from forets_native_run_20260911 import static_ready
    for block in (1,2):static_ready(root/'code',block)
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    return build,p


def freeze(root):
    from readout_edit_scope_20260914 import FILES
    build=read(root/'build.json')
    record=dict(root=str(root.resolve()),source_tree=build['source_tree'],prepared_sha256=build['prepared_sha256'],
        readers={n:sha(Path(__file__).with_name(n).read_bytes()) for n in FILES})
    print(json.dumps(dict(readout_plan_sha256=write(root/'readout-plan.json',encode(record)))))


def route(root):
    checked(root)
    # The inherited route receipt also contains the unused critic's public
    # catalog metadata. No critic request is sent in either experimental arm.
    from forets_context_judge_20260912 import checked_catalog
    import requests
    r=requests.get('https://openrouter.ai/api/v1/models/qwen/qwen3-coder-plus/endpoints',timeout=(10,30),allow_redirects=False)
    r.raise_for_status();write(root/'block-1.plus-catalog.json',encode(checked_catalog(r.json())))
    for block in (1,2):
        p=subprocess.run([sys.executable,'-B',str(root/'code/forets_native_run_20260911.py'),'route','--block',str(block)],
            capture_output=True,text=True,timeout=350)
        write(root/f'route-{block}.private.log',(p.stdout+'\n'+p.stderr).encode())
        print(json.dumps(dict(block=block,rc=p.returncode,receipt=(root/f'block-{block}.route.json').exists())),flush=True)
        if p.returncode:raise RuntimeError('route failure; no retry/GPU submission')


def submit(root):
    build,p=checked(root)
    from forets_paid_budget_20260911 import snapshot
    from forets_stage_gate import validate_route_receipt
    state=snapshot(root/'paid.sqlite')
    if state['stopped'] or state['unresolved']!=2:raise ValueError('budget gate')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],text=True,timeout=25)
    if len(queue.splitlines())>2:raise ValueError('two job slots not available')
    for block in (1,2):validate_route_receipt(root/f'block-{block}.route.json',root/'source')
    record=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_tree=build['source_tree'],controller_commit=build['commit'],
        planned_runs=16,paired_task_seeds=8,search_seconds=1200,execution_timeout=300,gpu_hours_cap=8,
        node='gpu28',gpu='RTX3090',gpus_per_block=1,cpus_per_block=6,blocks=2,prior_unknowns_carried=2,
        initial_execution_charged=True,only_edit_scope_varies=True,agent_model_updates=False,
        protected_cohort_read=False,original_interpreter_and_image=True,automatic_retry=False,
        readout_plan_sha256=sha((root/'readout-plan.json').read_bytes()),
        billing={k:v for k,v in state.items() if k!='scopes'},
        launchers={str(b):sha((root/f'launchers/edit-scope-b{b}.sbatch').read_bytes()) for b in (1,2)})
    write(root/'preflight.json',encode(record))
    for block in (1,2):
        intent=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),block=block,launcher_sha256=record['launchers'][str(block)])
        write(root/f'submit-intent-b{block}.json',encode(intent))
        result=subprocess.run(['sbatch','--parsable','--output='+str(root/f'slurm-b{block}-%j.out'),
            '--error='+str(root/f'slurm-b{block}-%j.err'),str(root/f'launchers/edit-scope-b{block}.sbatch')],capture_output=True,text=True,timeout=25)
        write(root/f'submit-response-b{block}.private.log',(result.stdout+'\n'+result.stderr).encode())
        job=result.stdout.strip().split(';')[0]
        if result.returncode or not re.fullmatch('[0-9]+',job):raise RuntimeError('ambiguous scheduler response; no retry')
        launch=dict(intent,job=job,package=str(root),source_tree=build['source_tree'],controller_commit=build['commit'])
        write(root/f'launch-b{block}.json',encode(launch));print(json.dumps(launch),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('freeze','route','submit'));p.add_argument('root',type=Path)
    a=p.parse_args();os.umask(0o077);globals()[a.mode](a.root.resolve(strict=True))
