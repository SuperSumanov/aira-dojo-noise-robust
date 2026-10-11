"""Conditional 2+6 capacity across two authorized3090 nodes, not a speedup test.

All model requests remain on the serving node's loopback. No new network service
exposure. This fixture diagnostic does not validate remote live-agent clients.
"""
import inspect,json,os,secrets,shutil,socket,subprocess,sys,time
from pathlib import Path
import joint_four_capacity_20261011 as f
from live_identity import cpu_topology as original_topology

ROOT=f.BASE/'resource-joint-two-node-20261011-v1'
DONOR=f.ROOT
PIN='fb949c4c6cbe9ee5d02ae467e45a08fb3b1409e01530555d4b0ccf7bdaaab0b2'
INTEGRATION=f.BASE/'resource-factory-integration-20261011-v2'
NAME=Path(__file__).name
r=f.r;s=f.s;d=f.d

def schedule():
    rows=[dict(index=0,block=0,slot=0,program=0,width=1,node='gpu3'),
          dict(index=1,block=1,slot=0,program=1,width=1,node='gpu27')]
    for b in (2,3):
        for slot in range(6):rows.append(dict(index=len(rows),block=b,slot=slot,program=(slot+b)%2,width=6,node='gpu3' if slot<2 else 'gpu27'))
    return rows

def topology():return [dict(**x,node=socket.gethostname().split('.')[0]) for x in original_topology()]

def node_cores(rows):return {(x['node'],x['socket'],x['core']) for x in rows}

def placement(service,service_cpu,workers,job):
    gpus=set(service['uuids']);cpus=node_cores(service_cpu);steps={service['step']}
    assert len(gpus)==2 and len(cpus)==8 and {x[0] for x in cpus}=={'gpu3'}
    for x in workers:
        g=set(x['gpu_uuids']);c=node_cores(x['cpu_topology'])
        assert len(g)==1 and len(c)==4 and not g&gpus and not c&cpus
        assert {a[0] for a in c}<={'gpu3','gpu27'} and len({a[0] for a in c})==1
        assert x['job']==job and x['step'] not in steps
        gpus|=g;cpus|=c;steps.add(x['step'])
    return dict(gpu_count=len(gpus),physical_cores=len(cpus),nodes=sorted({x[0] for x in cpus}))

def controller_source(source):
    a="['srun','--exclusive','--ntasks=1','--gres=gpu:1'"
    b="['srun','--exclusive','--nodes=1','--nodelist='+row['node'],'--ntasks=1','--gres=gpu:1'"
    assert source.count(a)==1;return source.replace(a,b)

def allocation_source(source):
    a="['srun','--exclusive','--ntasks=1','--gres=gpu:2'"
    b="['srun','--exclusive','--nodes=1','--nodelist=gpu3','--ntasks=1','--gres=gpu:2'"
    assert source.count(a)==1;return source.replace(a,b)

def activate():
    for mod in (f,f.g,f.g.g,f.g.g.s,f.g.g.m,f.e,r,s,d):mod.ROOT=ROOT;mod.NAME=NAME
    r.CAP=2400;r.schedule=schedule;r.cpu_topology=topology;r.validate_block=placement
    exec(compile(controller_source(inspect.getsource(r.controller)),'two-node-controller','exec'),r.__dict__)
    exec(compile(allocation_source(inspect.getsource(r.allocation)),'two-node-service','exec'),r.__dict__)

def prepare():
    assert d.sha(DONOR/'plan.json')==PIN and f.e.read(DONOR/'audit-v1.json')['full_capacity_gate']
    assert f.e.read(INTEGRATION/'audit-v1.json')['gate'], 'factory integration prerequisite not passed'
    p=f.e.read(DONOR/'plan.json')
    assert all(d.sha(DONOR/n)==h for n,h in p['files'].items())
    assert all(d.sha(n)==h for n,h in p['input_files'].items())
    assert d.sha(d.IMAGE)==p['task_image_sha256'] and d.sha(s.VLLM)==p['service_image_sha256']
    assert all(d.sha(n)==h for n,h in p['model_files'].items())
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        if n=='run.sbatch' or n.startswith('episode-'):continue
        dest=ROOT/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dest)
    for n in (NAME,'joint_two_node_readout_20261011.py'):
        shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    for row in schedule():
        ep=ROOT/f"episode-{row['index']}";(ep/'input_cache').mkdir(parents=True)
        shutil.copytree(DONOR/'episode-0/observer',ep/'observer',ignore=shutil.ignore_patterns('__pycache__'))
    (ROOT/'service-cache/tmp').mkdir(parents=True)
    with (ROOT/'.service.env').open('x') as file:file.write('VLLM_API_KEY='+secrets.token_hex(32)+'\n')
    os.chmod(ROOT/'.service.env',0o600)
    batch=f'''#!/bin/bash
#SBATCH --job-name=joint-two-node
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist=gpu3,gpu27
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=20
#SBATCH --hint=nomultithread
#SBATCH --time=00:40:00
#SBATCH --no-requeue
#SBATCH --output={ROOT}/allocation.private.log
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=20s 2340s {d.PY} -B {ROOT}/{NAME} allocation
'''
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    subprocess.run([str(d.PY),'-B',str(ROOT/NAME),'preflight'],check=True)
    p.update(schedule=schedule(),planned=14,planned_requests=14,gpus=8,execution_gpus=6,service_gpus=2,
        cpus=40,reserved_physical_cpus_per_node=20,active_worker_and_service_cpus=32,nodes=['gpu3','gpu27'],node=None,
        allocation_seconds_cap=2400,gpu_seconds_cap=19200,donor_plan_sha256=PIN,
        integration_prerequisite_sha256=d.sha(INTEGRATION/'audit-v1.json'),
        question='Can two local model GPUs coexist with6 actual mixed GPU programs across2 authorized3090 nodes?',
        acceptance='14/14 programs and14short requests,7outputs/source all21comparisons/source<=1e-5,8distinct allocated GPUs/node-qualified32CPU cores,all steps/cleanup/cost and both-node pressure records.',
        intervention='Deployment topology only for capability;2service+2execution on gpu3,4execution on gpu27. Each original program unchanged. Model requests execute on gpu3 loopback.',
        boundary='Two-node capability,not same-host2+6 or historical EAGAIN fix.512token requests can truncate;not remote production agent transport,6distincttasks,newseed,speedup or quality.',
        files={str(x.relative_to(ROOT)):d.sha(x) for x in ROOT.rglob('*') if x.is_file() and x.name!='.service.env' and '__pycache__' not in x.parts})
    d.write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,planned=14,plan_sha256=d.sha(ROOT/'plan.json'),gpu_seconds_cap=19200)))

def node_pressure():
    assert socket.gethostname().split('.')[0]=='gpu27'
    with (ROOT/'gpu27-pressure.jsonl').open('x') as file:
        while not (ROOT/'allocation-closed.json').exists():
            file.write(json.dumps(d.resource_pressure.snapshot())+'\n');file.flush();time.sleep(1)

def allocation():
    assert socket.gethostname().split('.')[0]=='gpu3'
    monitor=None
    try:
        with (ROOT/'node-monitor.private.log').open('x') as log:
            monitor=subprocess.Popen(['srun','--exclusive','--nodes=1','--nodelist=gpu27','--ntasks=1','--gres=gpu:0','--cpus-per-task=1','--hint=nomultithread',str(d.PY),'-B',str(ROOT/NAME),'node-pressure'],stdout=log,stderr=log,start_new_session=True)
            until=time.monotonic()+30
            while not (ROOT/'gpu27-pressure.jsonl').exists():
                if monitor.poll() is not None or time.monotonic()>until:raise RuntimeError('second-node monitor unavailable')
                time.sleep(.2)
            return r.allocation()
    finally:
        s.stop_owned(monitor)
        d.write(ROOT/'node-monitor-closed.json',dict(stopped=monitor is None or monitor.poll() is not None))

if __name__=='__main__':
    os.umask(0o077);mode=sys.argv[1]
    if mode=='prepare':prepare()
    else:
        activate()
        if mode=='preflight':
            d.configure()
            from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
            assert len(schedule())==14 and callable(JupyterCodeExecutor.execute_code)
        elif mode=='allocation':sys.exit(allocation())
        elif mode=='worker':sys.exit(f.g.g.worker(int(sys.argv[2])))
        elif mode=='service':sys.exit(r.service())
        elif mode=='node-pressure':node_pressure()
        else:raise ValueError(mode)
