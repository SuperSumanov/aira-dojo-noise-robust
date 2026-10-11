"""Observe actual GPU execution startup without changing its CLI or program."""
import ast
from collections import Counter
import json,os,shutil,subprocess,sys,time
from pathlib import Path
import execution_six_20261011 as e
from protocol_cli_capture_20261011 import SITE

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'resource-execution-protocol-six-20261011-v1'
DONOR=BASE/'resource-execution-six-20261011-v1'
PIN='ad15a37d6fba6e2d4f0f71d97daf7dfd03b0806965d42dde571d6499fd7cf42f'
OBSERVER=BASE/'resource-kernel-cli-capture-20261011-v1'
OBSERVER_PIN='3605debc1dc7678ad71d2fc06478f7343f3c45956970ad012dc20d459ab3a378'
NAME=Path(__file__).name
for mod in (e,e.r,e.r.s,e.r.s.d):mod.ROOT=ROOT;mod.NAME=NAME

def prepare():
    assert e.sha(DONOR/'plan.json')==PIN and e.read(DONOR/'closed.json')['complete']==0
    assert e.sha(OBSERVER/'plan.json')==OBSERVER_PIN and e.read(OBSERVER/'audit-v1.json')['complete']==48
    p=e.read(DONOR/'plan.json');op=e.read(OBSERVER/'plan.json')
    assert all(e.sha(DONOR/n)==h for n,h in p['files'].items())
    assert all(e.sha(OBSERVER/n)==h for n,h in op['files'].items())
    assert all(e.sha(n)==h for n,h in p['input_files'].items())
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        if n in ('run.sbatch',):continue
        dest=ROOT/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dest)
    for n in (NAME,'protocol_cli_capture_20261011.py'):
        shutil.copyfile(Path(__file__).with_name(n),ROOT/n)
    shutil.copyfile(OBSERVER/'readiness_transport_trial.py',ROOT/'readiness_transport_trial.py')
    for row in e.schedule():
        ep=ROOT/f"episode-{row['index']}";(ep/'input_cache').mkdir(parents=True,exist_ok=True)
        (ep/'observer').mkdir()
        (ep/'observer/sitecustomize.py').write_text(SITE)
        shutil.copyfile(OBSERVER/'block-0-worker-0/observer/gateway_counter.py',ep/'observer/gateway_counter.py')
    batch=(DONOR/'run.sbatch').read_text()
    assert str(DONOR) in batch and 'execution_six_20261011.py' in batch
    batch=batch.replace(str(DONOR),str(ROOT)).replace('execution_six_20261011.py',NAME).replace('--job-name=execution-six','--job-name=execution-protocol-six')
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    subprocess.run([str(e.r.s.d.PY),'-B',str(ROOT/NAME),'preflight'],check=True)
    p.update(donor_plan_sha256=PIN,observer_plan_sha256=OBSERVER_PIN,
        question='Locate protocol failure under unchanged real GPU execution; conditionally complete original narrow six-execution capacity matrix',
        instrumentation='Original CLI plus enum observer in exec child; transparent original client wait observer; successful-call warning enums retained.',
        readiness_overlay='Existing pipe-readiness fix only; no timeout increase, retry, reconnection or interpreter/image change.',
        boundary='New independently closed diagnostic; observer may affect timing. Not a root-cause repair,2+6 joint capacity,independent task/seed,speedup or quality result.',
        files={str(f.relative_to(ROOT)):e.sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    e.write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,planned=14,gpu_seconds_cap=10800,plan_sha256=e.sha(ROOT/'plan.json'))))

def observer_class(source):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='Observer')
    scope=dict(Counter=Counter,time=time)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'existing-enum-observer','exec'),scope)
    return scope['Observer']

def configure_preserving_device():
    # The donor probes CUDA before configure() clears its CPU-diagnostic mask.
    # Observer installation must not move that clearing ahead of the probe.
    device=os.environ.get('CUDA_VISIBLE_DEVICES')
    e.r.s.d.configure()
    if device is None:os.environ.pop('CUDA_VISIBLE_DEVICES',None)
    else:os.environ['CUDA_VISIBLE_DEVICES']=device

def install(ep):
    configure_preserving_device()
    from dojo.core.interpreters.jupyter import singularity_jupyter_server as server
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    build=server._build_singularity_command
    def observe_command(**kw):
        env=dict(kw['container_env']);assert 'PYTHONPATH' not in env
        env['PYTHONPATH']='/workspace/observer'
        return build(**dict(kw,container_env=env))
    server._build_singularity_command=observe_command
    original=JupyterKernelClient.wait_for_ready
    Observer=observer_class((ROOT/'readiness_transport_trial.py').read_text());calls=[]
    def observed(self,timeout_seconds=None):
        proxy=Observer(self);started=time.monotonic();ok=None;error=None
        try:ok=original(proxy,timeout_seconds);return ok
        except Exception as exc:error=type(exc).__name__;raise
        finally:calls.append(dict(ready=ok,error_type=error,seconds=time.monotonic()-started,**proxy.state()))
    JupyterKernelClient.wait_for_ready=observed
    return calls

def worker(index):
    ep=ROOT/f'episode-{index}';calls=install(ep)
    try:return e.worker(index)
    finally:e.write(ep/'protocol-calls.json',calls)

if __name__=='__main__':
    os.umask(0o077)
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        e.r.s.d.configure()
        from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
        assert callable(JupyterCodeExecutor.execute_code)
        assert e.ROOT==e.r.ROOT==e.r.s.ROOT==e.r.s.d.ROOT==ROOT
        e.write(ROOT/'protocol-entry-preflight.json',dict(imports_pass=True,no_kernel_started=True,no_model=True))
    elif sys.argv[1]=='worker':sys.exit(worker(int(sys.argv[2])))
    elif sys.argv[1]=='allocation':sys.exit(e.controller())
    else:raise ValueError('mode')
