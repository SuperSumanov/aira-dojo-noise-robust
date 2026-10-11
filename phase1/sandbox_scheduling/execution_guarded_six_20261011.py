"""Fourteen original GPU executions with bounded restart-aware failure handling.

Capability/diagnostic batch, not a randomized throughput comparison. All old
failed denominators stand; no candidate is retried or replaced in this batch.
"""
import json,os,shutil,subprocess,sys
from pathlib import Path
import execution_exit_capture_20261011 as g
from kernel_restart_guard import overlay

e=g.m.e
DONOR=g.BASE/'resource-execution-exit-capture-20261011-v1'
PIN='64d4d03d1b4513bfac11518736671031691f334334195e134eab564ba99931f0'
GUARD=g.BASE/'resource-restart-guard-trial-20261011-v2'
GUARD_PIN='4a27286e2480951f8b0114107f751e3cc8685a2317226038dccf22430f979929'
ROOT=g.BASE/'resource-execution-guarded-six-20261011-v1'
NAME=Path(__file__).name
CLIENT='source/src/dojo/core/interpreters/jupyter/jupyter_client.py'

def schedule():
    return [dict(index=i,block=b,slot=s,program=1,width=w) for i,(b,s,w) in enumerate(
        [(0,0,1),(1,0,1)]+[(b,s,6) for b in (2,3) for s in range(6)])]

def activate():
    for mod in (g,g.s,g.m,e,e.r,e.r.s,e.r.s.d):mod.ROOT=ROOT;mod.NAME=NAME
    e.schedule=schedule

def prepare():
    assert e.sha(DONOR/'plan.json')==PIN and e.read(DONOR/'audit-v1.json')['complete']==10
    assert e.sha(GUARD/'plan.json')==GUARD_PIN and e.read(GUARD/'audit-v1.json')['gate'] is True
    p=e.read(DONOR/'plan.json');assert all(e.sha(DONOR/n)==h for n,h in p['files'].items())
    assert all(e.sha(n)==h for n,h in p['input_files'].items())
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        if n=='run.sbatch' or n.startswith('episode-'):continue
        dst=ROOT/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dst)
    for n in (NAME,'kernel_restart_guard.py','kernel_shutdown_guard.py'):
        shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    (ROOT/CLIENT).write_text(overlay((ROOT/CLIENT).read_text()))
    for row in schedule():
        ep=ROOT/f"episode-{row['index']}";(ep/'input_cache').mkdir(parents=True);(ep/'observer').mkdir()
        (ep/'observer/sitecustomize.py').write_text(g.SITE+'    import kernel_shutdown_guard\n')
        for n in ('gateway_counter.py','kernel_lifecycle_observer.py'):
            shutil.copyfile(DONOR/'episode-0/observer'/n,ep/'observer'/n)
        shutil.copyfile(ROOT/'kernel_shutdown_guard.py',ep/'observer/kernel_shutdown_guard.py')
    batch=(DONOR/'run.sbatch').read_text().replace(str(DONOR),str(ROOT)).replace('execution_exit_capture_20261011.py',NAME)
    for a,b in (('#SBATCH --gres=gpu:1','#SBATCH --gres=gpu:6'),('#SBATCH --cpus-per-task=4','#SBATCH --cpus-per-task=24'),('#SBATCH --job-name=execution-exit-capture','#SBATCH --job-name=execution-guarded-six')):
        assert batch.count(a)==1;batch=batch.replace(a,b)
    assert str(ROOT/NAME) in batch
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    subprocess.run([str(e.r.s.d.PY),'-B',str(ROOT/NAME),'preflight'],check=True)
    p.update(question='Can6 unchanged GPU programs execute and clean up with restart-aware lifecycle handling,and do real native exits explain any failure?',
        schedule=schedule(),planned=14,gpus=6,cpus=24,gpu_seconds_cap=10800,allocation_seconds_cap=1800,
        donor_plan_sha256=PIN,guard_validation_plan_sha256=GUARD_PIN,
        instrumentation='Same provisioner exit observer,client/CLI enums and assigned-GPU2s telemetry as17567;no faulthandler.',
        intervention='Parentless restart/dead invalidates execution;gateway waits pending ready before shutdown<=15s. No candidate retries,timeout or source/input/image changes.',
        acceptance='14/14 including2serial then2six-way blocks;distinct6GPU/24physicalCPU sets;588steps each;91pairwise output comparisons<=1e-5;clean teardown and entire allocation cost. First failure closes remainder.',
        boundary='One original UNet/source family/seed42 on public synthetic fixture;not six distinct tasks,model service joint capacity,EAGAIN causal proof,speedup or quality.',
        files={str(f.relative_to(ROOT)):e.sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    e.write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,planned=14,plan_sha256=e.sha(ROOT/'plan.json'),gpu_seconds_cap=10800)))

if __name__=='__main__':
    os.umask(0o077);activate()
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        e.r.s.d.configure()
        import inspect
        from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
        assert 'gateway lifecycle event' in inspect.getsource(JupyterKernelClient.execute)
        assert all(x.ROOT==ROOT and x.NAME==NAME for x in (g,g.s,g.m,e,e.r,e.r.s,e.r.s.d))
        assert len(e.schedule())==14 and [len([x for x in schedule() if x['block']==b]) for b in range(4)]==[1,1,6,6]
        e.write(ROOT/'guarded-entry-preflight.json',dict(imports_pass=True,no_kernel=True,schedule_pass=True))
    elif sys.argv[1]=='worker':sys.exit(g.worker(int(sys.argv[2])))
    elif sys.argv[1]=='allocation':sys.exit(e.controller())
