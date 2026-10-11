"""Two local serving GPUs + four true task GPUs, ten frozen mixed executions."""
import ast,inspect,json,os,secrets,shutil,subprocess,sys
from pathlib import Path
import execution_guarded_six_20261011 as g

e=g.e;r=e.r;s=r.s;d=s.d
BASE=d.BASE;ROOT=BASE/'resource-joint-four-capacity-20261011-v1'
DONOR=BASE/'resource-execution-guarded-six-20261011-v1'
PIN='d96fba91f303325714b8a7320571776cbec66a87ccaa45f12d01afd5a2b418a5'
MODEL_DONOR=BASE/'resource-six-gpu-capacity-20261011-v2'
MODEL_PIN='024b608742e3934a8e716bd4c867243cf1f76be9c4439e25f19b9e54930f2120'
NAME=Path(__file__).name

def schedule():
    rows=[dict(index=0,block=0,slot=0,program=0,width=1),dict(index=1,block=1,slot=0,program=1,width=1)]
    for b in (2,3):
        for slot in range(4):rows.append(dict(index=len(rows),block=b,slot=slot,program=(slot+b)%2,width=4))
    return rows

def controller_source(source):
    for old,new in (('planned=14','planned=10'),('complete!=14','complete!=10'),('for x in requests)!=14','for x in requests)!=10')):
        assert source.count(old)==1,(old,source.count(old));source=source.replace(old,new)
    return source

def activate():
    for mod in (g,g.g,g.g.s,g.g.m,e,r,s,d):mod.ROOT=ROOT;mod.NAME=NAME
    r.schedule=schedule;r.CAP=2400
    src=controller_source(inspect.getsource(r.controller));exec(compile(src,'same-controller-ten-two-plus-four','exec'),r.__dict__)

def prepare():
    assert d.sha(DONOR/'plan.json')==PIN and e.read(DONOR/'audit-v1.json')['execution_gate']
    assert d.sha(MODEL_DONOR/'plan.json')==MODEL_PIN
    p=e.read(DONOR/'plan.json');model=e.read(MODEL_DONOR/'plan.json')
    assert all(d.sha(DONOR/n)==h for n,h in p['files'].items())
    assert all(d.sha(n)==h for n,h in p['input_files'].items())
    assert d.sha(s.VLLM)==model['service_image_sha256']
    assert all(d.sha(n)==h for n,h in model['model_files'].items())
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        if n=='run.sbatch' or n.startswith('episode-'):continue
        dst=ROOT/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dst)
    shutil.copyfile(__file__,ROOT/NAME)
    # Existing service donor has a node sanity check; change exactly that check.
    server=ROOT/'service_thread_diag_20261011.py';src=server.read_text()
    assert src.count("== 'gpu1'")==1
    server.write_text(src.replace("== 'gpu1'","== 'gpu3'",1))
    for row in schedule():
        ep=ROOT/f"episode-{row['index']}";(ep/'input_cache').mkdir(parents=True);(ep/'observer').mkdir()
        for n in ('sitecustomize.py','gateway_counter.py','kernel_lifecycle_observer.py','kernel_shutdown_guard.py'):
            shutil.copyfile(DONOR/'episode-0/observer'/n,ep/'observer'/n)
    (ROOT/'service-cache/tmp').mkdir(parents=True)
    with (ROOT/'.service.env').open('x') as f:f.write('VLLM_API_KEY='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    batch=f'''#!/bin/bash
#SBATCH --job-name=joint-two-plus-four
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:6
#SBATCH --cpus-per-task=24
#SBATCH --hint=nomultithread
#SBATCH --time=00:40:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 2340s {d.PY} -B {ROOT}/{NAME} allocation
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    subprocess.run([str(d.PY),'-B',str(ROOT/NAME),'preflight'],check=True)
    p.update(question='Can the fixed local27B service coexist with4 actual mixed GPU training programs without resource errors?',
        schedule=schedule(),planned=10,planned_requests=10,gpus=6,execution_gpus=4,service_gpus=2,cpus=24,service_cpus=8,worker_cpus=4,
        allocation_seconds_cap=2400,gpu_seconds_cap=14400,node='gpu3',donor_plan_sha256=PIN,model_donor_plan_sha256=MODEL_PIN,
        source_families=2,model_files=model['model_files'],service_image_sha256=model['service_image_sha256'],
        no_model=False,no_api=False,no_paid_api=True,no_base_training=True,local_loopback_only=True,
        service_model='qwen3.8-27b',reasoning_effort_requested='medium',max_tokens=512,model_seed=49,
        source_policy='Original2programs,150CNN/588UNet steps,seed42,450s limit,image,input unchanged;public fixtures,no hidden labels.',
        intervention='Joint capacity diagnostic: lifecycle fixes already validated;no algorithm modifications,no global limit change,no retries.',
        acceptance='10/10 programs+local requests;5outputs/source all10 comparisons/source<=1e-5;6distinct GPU and24CPU sets in4way blocks;no error flags,full cleanup,cost.',
        stop='Any serial or block failure closes remaining fixed matrix;no replacements.',
        boundary='2+4 not2+6. Synthetic/public fixtures of2source families,not newtask/seed or realagent-quality/throughput result;requests may end length512.',
        files={str(f.relative_to(ROOT)):d.sha(f) for f in ROOT.rglob('*') if f.is_file() and f.name!='.service.env' and '__pycache__' not in f.parts})
    d.write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,planned=10,requests=10,plan_sha256=d.sha(ROOT/'plan.json'),gpu_seconds_cap=14400)))

def worker(index):
    # Same task wrapper, private cache and observers as the complete6GPU batch.
    return g.g.worker(int(index))

if __name__=='__main__':
    os.umask(0o077);activate()
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        d.configure()
        from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
        assert len(r.schedule())==10 and r.CAP==2400
        assert all(mod.ROOT==ROOT and mod.NAME==NAME for mod in (g,g.g,g.g.s,g.g.m,e,r,s,d))
        assert "== 'gpu3'" in inspect.getsource(s.service)
        d.write(ROOT/'joint-entry-preflight.json',dict(imports=True,no_kernel=True,no_model=True,schedule=True))
    elif sys.argv[1]=='worker':sys.exit(worker(sys.argv[2]))
    elif sys.argv[1]=='service':sys.exit(r.service())
    elif sys.argv[1]=='allocation':sys.exit(r.allocation())
