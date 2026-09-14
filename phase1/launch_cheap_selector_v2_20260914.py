"""Freeze, current route check and one-shot dispatch for the exact new matrix."""
import argparse,datetime as dt,json,os,re,subprocess,sys
from pathlib import Path
from forets_environment_build_20260912 import read,write,encode,sha
def checked(root):
    build=read(root/'build.json');p=read(root/'prepared.json',build['prepared_sha256'])
    if p['run_count']!=12 or build['runs']!=12 or p['nominal_gpu_hours']!=170/60:raise ValueError('new fixed matrix')
    aborted=read(root.parent/'forets-wallclock-20260912-q_imzdb_'/'infrastructure-abort.json','a775e0d9a6dcf62accf055f31ebd6822fcf9b06a2adf225b16c03ada227ea8e7')
    if aborted['allocation_seconds']!=134 or p['nominal_gpu_hours']+134/3600>3:raise ValueError('combined attempt resource cap')
    integration=read(root/'cheap-integration.json')
    if integration['status']!='PASSED_ACTUAL_CHEAP_SELECTOR_BATCH' or integration['source_tree']!=build['source_tree'] or len(integration['rows'])!=12:raise ValueError('actual integration')
    cutoff=read(root/'integration-check.json')
    if cutoff['status']!='PASSED_CPU_INTEGRATION_NOT_GPU_ACCEPTANCE' or cutoff['source_tree']!=build['source_tree']:raise ValueError('cutoff/controller integration')
    sys.path[:0]=[str(root/'code'),str(root/'source/src')]
    from forets_native_run_20260911 import static_ready
    for block in (1,2):static_ready(root/'code',block)
    os.environ['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    return build,p
def freeze(root):
    from readout_cheap_selector_20260914 import FILES
    build=read(root/'build.json')
    record=dict(root=str(root.resolve()),source_tree=build['source_tree'],prepared_sha256=build['prepared_sha256'],readers={n:sha(Path(__file__).with_name(n).read_bytes()) for n in FILES})
    print(json.dumps(dict(readout_plan_sha256=write(root/'readout-plan.json',encode(record)))))
def route(root):
    checked(root)
    # Inherited route also checks unused public catalog metadata, not an 8B model.
    from forets_context_judge_20260912 import checked_catalog
    import requests
    response=requests.get('https://openrouter.ai/api/v1/models/qwen/qwen3-coder-plus/endpoints',timeout=(10,30),allow_redirects=False)
    response.raise_for_status();write(root/'block-1.plus-catalog.json',encode(checked_catalog(response.json())))
    for block in (1,2):
        r=subprocess.run([sys.executable,'-B',str(root/'code/forets_native_run_20260911.py'),'route','--block',str(block)],capture_output=True,text=True,timeout=350)
        write(root/f'route-{block}.private.log',(r.stdout+'\n'+r.stderr).encode())
        print(json.dumps(dict(block=block,rc=r.returncode,receipt=(root/f'block-{block}.route.json').exists())),flush=True)
        if r.returncode:raise RuntimeError('route failed, no blind retry')
def submit(root):
    build,p=checked(root)
    from forets_paid_budget_20260911 import snapshot
    from forets_stage_gate import validate_route_receipt
    state=snapshot(root/'paid.sqlite')
    if state['stopped'] or state['unresolved']!=2 or state['accounted_usd']+1.4>10:raise ValueError('cumulative budget headroom')
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],text=True,timeout=25)
    if len(queue.splitlines())>2:raise ValueError('two job slots not free')
    for block in (1,2):validate_route_receipt(root/f'block-{block}.route.json',root/'source')
    image=Path('/research/d7/spc/yzyang4/aira-dojo/build/superimage/superimage.root.2026-07-macos-v1.sif');st=image.stat()
    if (st.st_size,st.st_mtime_ns)!=(19717783552,1784638286000000000):raise ValueError('original image changed')
    # Existing real fresh-container qualification is reused, never rerun as G0.
    read(root.parent/'forets-fresh-integration-20260914-ih6u0mpw/result.json','4b7e059c43cd266778e80ff22a776ba4de5cc2e74e8007ae94f68f28a7ff789b')
    record=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),source_tree=build['source_tree'],controller_commit=build['commit'],planned_runs=12,paired_triples=4,
        search_seconds=600,adapter_attempt_cap=100,execution_timeout=300,gpu_hours_cap=170/60,prior_aborted_seconds=134,combined_gpu_hours_cap=3,node='gpu28',gpu='RTX3090',gpus_per_block=1,cpus_per_block=6,
        only_selector_differs_within_triples=True,common_backend='fresh_container_ipython',agent_updates=False,protected_cohort_read=False,automatic_retry=False,
        readout_plan_sha256=sha((root/'readout-plan.json').read_bytes()),billing={k:v for k,v in state.items() if k!='scopes'},
        launchers={str(b):sha((root/f'launchers/cheap-b{b}.sbatch').read_bytes()) for b in (1,2)})
    write(root/'preflight.json',encode(record))
    for block in (1,2):
        intent=dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),block=block,launcher_sha256=record['launchers'][str(block)])
        write(root/f'submit-intent-b{block}.json',encode(intent))
        r=subprocess.run(['sbatch','--parsable','--output='+str(root/f'slurm-b{block}-%j.out'),'--error='+str(root/f'slurm-b{block}-%j.err'),str(root/f'launchers/cheap-b{block}.sbatch')],capture_output=True,text=True,timeout=25)
        write(root/f'submit-response-b{block}.private.log',(r.stdout+'\n'+r.stderr).encode());job=r.stdout.strip().split(';')[0]
        if r.returncode or not re.fullmatch('[0-9]+',job):raise RuntimeError('ambiguous submission; no retry')
        launch=dict(intent,job=job,package=str(root),source_tree=build['source_tree'],controller_commit=build['commit'])
        write(root/f'launch-b{block}.json',encode(launch));print(json.dumps(launch),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('freeze','route','submit'));p.add_argument('root',type=Path);a=p.parse_args();os.umask(0o077);globals()[a.mode](a.root.resolve(strict=True))
