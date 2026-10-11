"""10 original serial executions maximum; capture real kernel exits, no watchdog."""
import json,os,shutil,subprocess,sys,threading
from pathlib import Path
import execution_stack_capture_20261011 as s

m=s.m;BASE=s.BASE
ROOT=BASE/'resource-execution-exit-capture-20261011-v1'
DONOR=BASE/'resource-execution-stack-capture-20261011-v1'
PIN='4741e0748c51affd413700690d1f3f24e879c522f194b74e5226a63917ca27b8'
NAME=Path(__file__).name
SITE="""import os,sys
if os.path.basename(sys.argv[0])=='jupyter-kernelgateway':
    import gateway_counter
    import kernel_lifecycle_observer
"""

def activate():
    s.ROOT=ROOT;s.NAME=NAME
    for mod in (m,m.e,m.e.r,m.e.r.s,m.e.r.s.d):mod.ROOT=ROOT;mod.NAME=NAME
    m.e.schedule=s.schedule

def prepare():
    assert m.e.sha(DONOR/'plan.json')==PIN and m.e.read(DONOR/'closed.json')['complete']==5
    p=m.e.read(DONOR/'plan.json')
    assert all(m.e.sha(DONOR/n)==h for n,h in p['files'].items())
    assert all(m.e.sha(n)==h for n,h in p['input_files'].items())
    ROOT.mkdir(mode=0o700)
    for n in p['files']:
        if n=='run.sbatch' or n.startswith('episode-'):continue
        dest=ROOT/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dest)
    for name in (NAME,'kernel_lifecycle_observer.py'):
        shutil.copyfile(Path(__file__).with_name(name),ROOT/name)
    for row in s.schedule():
        ep=ROOT/f"episode-{row['index']}";(ep/'input_cache').mkdir(parents=True);(ep/'observer').mkdir()
        (ep/'observer/sitecustomize.py').write_text(SITE)
        shutil.copyfile(DONOR/'episode-0/observer/gateway_counter.py',ep/'observer/gateway_counter.py')
        shutil.copyfile(ROOT/'kernel_lifecycle_observer.py',ep/'observer/kernel_lifecycle_observer.py')
    batch=(DONOR/'run.sbatch').read_text().replace(str(DONOR),str(ROOT)).replace('execution_stack_capture_20261011.py',NAME)
    batch=batch.replace('--job-name=execution-stack-capture','--job-name=execution-exit-capture')
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    subprocess.run([str(m.e.r.s.d.PY),'-B',str(ROOT/NAME),'preflight'],check=True)
    p.update(question='Does the kernel die/restart during an apparently stalled original execution,and which process exit code?',
        donor_plan_sha256=PIN,instrumentation='Original CLI/client counters, provisioner launch/exit enums and assigned-GPU2s NVML. No faulthandler watchdog.',
        acceptance='Diagnostic localization only,10original serial maximum,first failure stops. Lifecycle observer must be installed and each attempted candidate has a launch event.',
        boundary='No watchdog in this batch; comparisons to17566 are instrumentation-confounded,not a causal repair or failure-rate estimate. Not6-way/model service/quality.',
        files={str(f.relative_to(ROOT)):m.e.sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    m.e.write(ROOT/'plan.json',p)
    print(json.dumps(dict(prepared=True,planned=10,gpu_seconds_cap=1800,plan_sha256=m.e.sha(ROOT/'plan.json'))))

def worker(index):
    ep=ROOT/f'episode-{index}';stop=threading.Event();observer=None
    try:
        probe=m.e.probe(False);m.e.write(ep/'exit-cuda-before.json',probe)
        assert probe.get('cuinit_rc')==0 and probe.get('visible_devices')==1
        device=probe['uuids'][0];before=s.gpu_snapshot(device);m.e.write(ep/'gpu-before.json',before)
        assert before['query_ok']
        def sample():
            with (ep/'gpu-monitor.jsonl').open('x') as f:
                while not stop.is_set():f.write(json.dumps(s.gpu_snapshot(device))+'\n');f.flush();stop.wait(2)
        observer=threading.Thread(target=sample,daemon=True);observer.start()
        # m.worker retains the unmodified prelude and original candidate source.
        return m.worker(index)
    except Exception as exc:
        m.e.write(ep/'exit-worker-error.json',dict(error_type=type(exc).__name__));return 2
    finally:
        stop.set()
        if observer:observer.join(timeout=10)

if __name__=='__main__':
    os.umask(0o077);activate()
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        m.e.r.s.d.configure()
        from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
        assert callable(JupyterCodeExecutor.execute_code)
        assert all(x.ROOT==ROOT and x.NAME==NAME for x in (s,m,m.e,m.e.r,m.e.r.s,m.e.r.s.d))
        m.e.write(ROOT/'exit-entry-preflight.json',dict(imports_pass=True,no_kernel=True))
    elif sys.argv[1]=='worker':sys.exit(worker(int(sys.argv[2])))
    elif sys.argv[1]=='allocation':sys.exit(s.controller())
