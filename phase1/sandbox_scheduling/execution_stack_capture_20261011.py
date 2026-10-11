"""Ten serial, unchanged UNet executions; first failure stops; diagnostic only."""
import csv,inspect,io,json,os,re,shutil,subprocess,sys,threading,time
from pathlib import Path
import execution_protocol_six_20261011 as m

BASE=Path('/research/d7/spc/yzyang4')
ROOT=BASE/'resource-execution-stack-capture-20261011-v1'
DONOR=BASE/'resource-execution-protocol-six-20261011-v1'
PIN='ee8e9295ba7cce669d7cd4d9d870b9d05b66bd597540632ab5dee3049944670f'
NAME=Path(__file__).name

STACK="""
import faulthandler as _r14_fault
_r14_fault_file=open('kernel-stack.private.log','w')
_r14_fault.dump_traceback_later(30,repeat=True,file=_r14_fault_file)
"""

def schedule():return [dict(index=i,block=i,slot=0,program=1,width=1) for i in range(10)]

def activate():
    for mod in (m,m.e,m.e.r,m.e.r.s,m.e.r.s.d):mod.ROOT=ROOT;mod.NAME=NAME
    m.e.schedule=schedule

def stack_executor(base,ep):
    observed=m.e_observe_original(base,ep)
    class StackObserved(observed):
        def execute_code(self,code,*args,**kwargs):
            count=getattr(self,'stack_call_count',0);self.stack_call_count=count+1
            return super().execute_code(code+STACK if count==0 else code,*args,**kwargs)
    return StackObserved

FIELDS=('utilization.gpu','memory.used','memory.total','power.draw','power.limit','temperature.gpu','pstate','clocks.current.sm')
def gpu_snapshot(device):
    assert re.fullmatch(r'GPU-[a-fA-F0-9-]+',device)
    row=dict(time=time.time(),query_ok=False)
    try:
        p=subprocess.run(['nvidia-smi','--id='+device,'--query-gpu='+','.join(FIELDS),'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8)
        row['returncode']=p.returncode
        if p.returncode:
            low=p.stderr.lower();row['error_categories']={k:k in low for k in ('permission','not found','no devices','not a valid field','failed to initialize','not supported')}
            return row
        records=list(csv.reader(io.StringIO(p.stdout)));assert len(records)==1 and len(records[0])==len(FIELDS)
        values=[x.strip() for x in records[0]]
        assert all(re.fullmatch(r'(?:[0-9.]+|P[0-9]+|\[N/A\])',x) for x in values)
        row.update(query_ok=True,values=dict(zip(FIELDS,values)))
    except Exception as exc:row['error_type']=type(exc).__name__
    return row

def prepare():
    assert m.e.sha(DONOR/'plan.json')==PIN and m.e.read(DONOR/'closed.json')['complete']==7
    old=m.e.read(DONOR/'plan.json');assert all(m.e.sha(DONOR/n)==h for n,h in old['files'].items())
    assert all(m.e.sha(n)==h for n,h in old['input_files'].items())
    ROOT.mkdir(mode=0o700)
    for n in old['files']:
        if n=='run.sbatch' or n.startswith('episode-'):continue
        dest=ROOT/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(DONOR/n,dest)
    shutil.copyfile(__file__,ROOT/NAME)
    for r in schedule():
        ep=ROOT/f"episode-{r['index']}";(ep/'input_cache').mkdir(parents=True);(ep/'observer').mkdir()
        for name in ('sitecustomize.py','gateway_counter.py'):
            shutil.copyfile(DONOR/'episode-0/observer'/name,ep/'observer'/name)
    batch=(DONOR/'run.sbatch').read_text().replace(str(DONOR),str(ROOT)).replace('execution_protocol_six_20261011.py',NAME)
    for a,b in (('--gres=gpu:6','--gres=gpu:1'),('--cpus-per-task=24','--cpus-per-task=4'),('--job-name=execution-protocol-six','--job-name=execution-stack-capture')):
        assert batch.count(a)==1;batch=batch.replace(a,b)
    (ROOT/'run.sbatch').write_text(batch);subprocess.run(['bash','-n',str(ROOT/'run.sbatch')],check=True)
    subprocess.run([str(m.e.r.s.d.PY),'-B',str(ROOT/NAME),'preflight'],check=True)
    old.update(question='Capture stacks and assigned-device telemetry during the unchanged candidate stall; not a repair or performance comparison.',
        schedule=schedule(),planned=10,gpus=1,cpus=4,gpu_seconds_cap=1800,allocation_seconds_cap=1800,donor_plan_sha256=PIN,
        instrumentation='Existing CLI/client observers plus30s faulthandler watchdog in kernel prelude and2s read-only NVML in assigned GPU step.',
        acceptance='Diagnostic localization only; record all10 planned including unstarted. First failure or missing device observer stops, no replacement.',
        boundary='Watchdog/observer may perturb timing; serial repetition is not six-way capacity or failure-rate estimation. Source,input,seed42,image and450s candidate timeout unchanged.',
        files={str(f.relative_to(ROOT)):m.e.sha(f) for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts})
    m.e.write(ROOT/'plan.json',old)
    print(json.dumps(dict(prepared=True,planned=10,gpu_seconds_cap=1800,plan_sha256=m.e.sha(ROOT/'plan.json'))))

def worker(index):
    ep=ROOT/f'episode-{index}';stop=threading.Event();observer=None;error=None
    try:
        probe=m.e.probe(False);m.e.write(ep/'stack-cuda-before.json',probe)
        assert probe.get('cuinit_rc')==0 and probe.get('visible_devices')==1
        device=probe['uuids'][0];before=gpu_snapshot(device);m.e.write(ep/'gpu-before.json',before)
        assert before['query_ok'],'device observer unavailable'
        def sample():
            with (ep/'gpu-monitor.jsonl').open('x') as f:
                while not stop.is_set():f.write(json.dumps(gpu_snapshot(device))+'\n');f.flush();stop.wait(2)
        observer=threading.Thread(target=sample,daemon=True);observer.start()
        m.e_observe_original=m.e.observe_executor;m.e.observe_executor=stack_executor
        return m.worker(index)
    except Exception as exc:
        error=type(exc).__name__;m.e.write(ep/'stack-worker-error.json',dict(error_type=error));return 2
    finally:
        stop.set()
        if observer:observer.join(timeout=10)

def controller():
    source=inspect.getsource(m.e.controller)
    for a,b in [('range(4)','range(10)'),('planned=14','planned=10'),('complete!=14','complete!=10')]:
        assert source.count(a)==1;source=source.replace(a,b)
    scope=dict(m.e.__dict__);exec(compile(source,'same-controller-ten-serial','exec'),scope)
    return scope['controller']()

if __name__=='__main__':
    os.umask(0o077);activate()
    if sys.argv[1]=='prepare':prepare()
    elif sys.argv[1]=='preflight':
        m.e.r.s.d.configure()
        from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
        assert callable(JupyterCodeExecutor.execute_code)
        assert all(x.ROOT==ROOT and x.NAME==NAME for x in (m,m.e,m.e.r,m.e.r.s,m.e.r.s.d))
        m.e.write(ROOT/'stack-entry-preflight.json',dict(imports_pass=True,no_kernel=True))
    elif sys.argv[1]=='worker':sys.exit(worker(int(sys.argv[2])))
    elif sys.argv[1]=='allocation':sys.exit(controller())
