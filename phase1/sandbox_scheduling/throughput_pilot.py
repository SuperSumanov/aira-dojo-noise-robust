"""R14 approved fixed-workload qualification: 6 sources x 2 widths x 3 repeats.

One 3090 allocation, 90 minutes INCLUDING setup/failures. No source edits,
quality grading, generator, API or base-model training. Related sources and
identical-seed restarts are not independent tasks or training seeds.
"""
from __future__ import annotations
import argparse
import ast
import concurrent.futures
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time

from lifecycle_pilot import sha, read, write, load, SECRET, RUNTIME_SHA

B = Path('/research/d7/spc/yzyang4')
R = B/'scheduling-throughput-20261007-v1'
D = B/'matched-representation-20261005-v1'
PY = B/'venvs/aira/bin/python'
NAME = 'throughput_pilot.py'
SEED = 130701
CPU = 6
SOURCES = [
    ('dec-xgb','tabular-playground-series-dec-2021','c7bc94f0237d85aaf1c89ad9f9630f34f71b7c134551095a3f02992172e08e5b',None),
    ('spooky-tfidf','spooky-author-identification','e8649e10bcb4d865cd2b9ec8926de069185e25e88a5d17fdb9cf5aa89dda529d','spooky-dsearch-dev-20260925-MmeYVo/tfidf-slot2-v1/candidate.py'),
    ('dec-cat-a','tabular-playground-series-dec-2021','6521355800cd0a91f07b43411b7ed3daf470f2081273e27ac9c38efdd63c2222',None),
    ('petfinder-lgb','petfinder-pawpularity-score','ca58ad6f31ce3f11b7a549b5c5a2a7d2ea431f2301a1fec51f6e5d2c29381a10','petfinder-dsearch-dev-20260925-vNWd8llx/replay-four-v1/slot-3/candidate.py'),
    ('dec-cat-b','tabular-playground-series-dec-2021','ba3378b8a32668608bc5c832fcafc81fc5b15cf5c647e2caf3b1c2211a4bbd91',None),
    ('spooky-union','spooky-author-identification','53a71860c621ae2352850399737560ee0287965ddb5e1ec6fa49e19ae704935a','spooky-dsearch-dev-20260925-MmeYVo/replay-union-v1/slot-5/candidate.py'),
]
DEVS = {
 'spooky-author-identification':('spooky-dsearch-dev-20260925-MmeYVo','fea394e46b91d873ec67f7a4c7d95857b44fb4e5d084d2159bb182b24db12723'),
 'petfinder-pawpularity-score':('petfinder-dsearch-dev-20260925-vNWd8llx','c55a42f6bba90f9e296a8808f0180c03d75448c2a700055c75587d20d704c7f4'),
}


def schedule():
    rows=[]
    for repeat in range(3):
        order=list(range(6))
        # Rotate the SAME GPU/CPU-alternating FIFO in both arms; not outcome-based.
        order=order[2*repeat:]+order[:2*repeat]
        for arm in (('serial','share2') if repeat%2==0 else ('share2','serial')):
            for program in order:
                rows.append(dict(index=len(rows),repeat=repeat,arm=arm,program=program,seed=SEED))
    return rows


def runtime():
    if sha(R/'runtime.py')!=RUNTIME_SHA: raise ValueError('runtime drift')
    m=load('throughput_runtime',R/'runtime.py');m.R=R;m.setup();return m


def check():
    p=read(R/'plan.json')
    if p['schedule']!=schedule() or p['gpu_hours_cap']!=1.5: raise ValueError('plan drift')
    for name,value in p['files'].items():
        if sha(R/name)!=value: raise ValueError('source drift')
    for value in p['public_inputs']:
        if sha(value['path'])!=value['sha256']: raise ValueError('public input drift')
    return p


def code_safe(raw):
    if SECRET.search(raw): raise ValueError('credential-shaped source')
    tree=ast.parse(raw.decode())
    # A narrow workload, not a security proof. Actual filesystem isolation remains mandatory.
    for n in ast.walk(tree):
        if isinstance(n,ast.Constant) and isinstance(n.value,str):
            if any(x in n.value.lower() for x in ('https://','http://','/research/','/mnt/','pip install','wget ','curl ')):
                raise ValueError('source outside offline dev scope')
    compile(tree,'candidate.py','exec')


def prepare(commit,node):
    if not re.fullmatch('[a-f0-9]{40}',commit) or node not in ('gpu27','gpu28'):raise ValueError('metadata')
    if sha(D/'plan.json')!='fed6f8c812fc49db8acc459b460a10bbe962cbe10b8a2172f5dff06c7686a624':raise ValueError('donor plan')
    donor=read(D/'plan.json')
    R.mkdir(mode=0o700,exist_ok=False)
    for name,expected in donor['files'].items():
        if name.startswith(('source/','forets_','opencl-vendors/')):
            if sha(D/name)!=expected:raise ValueError('donor drift')
            dest=R/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dest)
    shutil.copyfile(D/'runtime.py',R/'runtime.py')
    for name in (NAME,'lifecycle_pilot.py','census.py'):
        shutil.copyfile(Path(__file__).with_name(name),R/name)
    c=load('throughput_census',R/'census.py')
    selected=json.loads(c.read_pinned(c.SAMPLE,'11b3f7c9c28119b612f332af6b6ddfc6fabd02a4f7694912576e615871ed8039'))['selected']
    needed={h for _,_,h,path in SOURCES if path is None};found={}
    for filename,expected in c.PINS.items():
        rows=[r for r in selected if r['task']=='tabular-playground-series-dec-2021' and r['file']==filename]
        if not rows:continue
        obj=json.loads(c.read_pinned(c.ROOT/filename,expected))
        for row in rows:
            for code in c.get_pair(obj,row):
                raw=code.encode();h=hashlib.sha256(raw).hexdigest()
                if h in needed:found[h]=raw
        del obj
    if set(found)!=needed:raise ValueError('fixed public source unavailable')
    (R/'programs').mkdir();(R/'data-dec').mkdir();(R/'empty-data').mkdir();(R/'bin').mkdir()
    programs=[]
    for i,(name,task,h,path) in enumerate(SOURCES):
        raw=(B/path).read_bytes() if path else found[h]
        if hashlib.sha256(raw).hexdigest()!=h:raise ValueError('source mismatch')
        code_safe(raw);(R/f'programs/{i}.py').write_bytes(raw)
        data=R/'data-dec' if task not in DEVS else B/DEVS[task][0]/'split-v1/public'
        programs.append(dict(name=name,task=task,source_sha256=h,data=str(data),expected_gpu=path is None))
    # Public training file only. Fixed prefix then seeded 80/10/10 split; not a quality benchmark.
    source=B/'mle-bench-data/tabular-playground-series-dec-2021/prepared/public/train.csv'
    with source.open(newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames;rows=[]
        for row in reader:
            rows.append(row)
            if len(rows)==5120:break
    if len(rows)!=5120 or fields[-1]!='Cover_Type':raise ValueError('public training shape')
    random.Random(SEED).shuffle(rows)
    train,query=rows[:4096],rows[4096:4608]
    for filename,columns,values in [('train.csv',fields,train),('test.csv',fields[:-1],[{k:r[k] for k in fields[:-1]} for r in query]),('sample_submission.csv',['Id','Cover_Type'],[{'Id':r['Id'],'Cover_Type':0} for r in query])]:
        with (R/'data-dec'/filename).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(values)
    public_inputs=[dict(path=str(source),sha256=sha(source))]
    for task,(dev,mh) in DEVS.items():
        manifest=B/dev/'split-v1/manifest.json'
        if sha(manifest)!=mh:raise ValueError('dev provenance drift')
        # Only public CSV bytes are accessed; no private labels or official test.
        public_inputs.append(dict(path=str(manifest),sha256=mh))
        for filename in ('train.csv','test.csv','sample_submission.csv'):
            path=B/dev/'split-v1/public'/filename
            if not path.exists():raise ValueError('public fixture missing')
            key={'train.csv':'train','test.csv':'test','sample_submission.csv':'sample'}[filename]
            if sha(path)!=read(manifest)['files_sha256'][key]:raise ValueError('dev public bytes no longer match provenance')
            public_inputs.append(dict(path=str(path),sha256=sha(path)))
    for row in schedule()+[dict(index=36)]:
        (R/f'episode-{row["index"]}/work').mkdir(parents=True)
    (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom throughput_pilot import task_runtime\ntask_runtime()\n')
    os.chmod(R/'bin/singularity',0o700)
    batch=f'''#!/bin/bash
#SBATCH --job-name=r14-fixed-throughput
#SBATCH --partition=gpu_24h
#SBATCH --account=gpu
#SBATCH --qos=gpu
#SBATCH --nodelist={node}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task={CPU}
#SBATCH --time=01:30:00
#SBATCH --no-requeue
set -euo pipefail
umask 077
export SLURM_CONF=/opt1/slurm/gpu-slurm.conf
export PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=15s 5360s srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task={CPU} --gres=gpu:1 --cpu-bind=cores {PY} -B {R}/{NAME} controller
'''
    (R/'run.sbatch').write_text(batch)
    plan=dict(source_commit=commit,node=node,schedule=schedule(),programs=programs,seed=SEED,
        gpu_hours_cap=1.5,allocation_seconds=5400,gpus=1,total_cpu=CPU,
        candidate_timeout_seconds=120,worker_hard_seconds=180,planned_executions=36,
        no_quality_scoring=True,no_api=True,no_base_training=True,public_inputs=public_inputs,
        dev_dec=dict(train=4096,query=512,unused=512,source='public train only',selection='first5120 then fixed-seed shuffle'),
        qualification='environment warmup, first serial block must complete all six including actual GPU trees; no replacement',
        claim='small dev fixed-workload throughput ONLY; three repeats are original-seed restarts',
        exclusions_before_freeze=['Spooky old rc1 slots3/4','Dec XGB fit-early-stopping API-risk source4244cbc2','neural weights unavailable'],
        files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()})
    write(R/'plan.json',plan)
    m=runtime()
    if sha(m.TASK_IMAGE)!='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda':raise ValueError('image drift')
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    cfg=JupyterInterpreterConfig(working_dir=str(R/'episode-0/work'),timeout=120,container_runtime='singularity',superimage_directory=str(m.TASK_IMAGE.parent),superimage_version='2026-07-macos-v1')
    cfg.validate();interp=build(cfg,INTERPRETER_MAP,data_dir=R/'data-dec')
    if not interp.factory or interp._instance is not None:raise ValueError('unexpected eager launch')
    subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
    write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),source_compile=True,lazy_config=True,unchanged_image=True,
        real_gpu_namespace_pending=True,dependency_versions_pending=True,whole_allocation_cap=True,
        failure_denominator=36,no_model_checkpoint_applicable=True,no_training_split_or_selection=True))
    print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'))))


def task_runtime():
    runtime()
    from forets_gpu_binding_20260911 import REAL_SINGULARITY,split_command,rewrite
    from forets_native_gpu_binding_20260911 import native_identity,resolve_native
    from forets_opencl_allowlist_20260911 import driver_binds
    args=sys.argv[1:]
    if args==['--version']:os.execv(REAL_SINGULARITY,[REAL_SINGULARITY,'--version'])
    split_command(args);ep=Path(os.environ['POLICY9B_EPISODE'])
    if ep.parent!=R or not re.fullmatch(r'episode-(?:[0-9]|[12][0-9]|3[0-6])',ep.name):raise ValueError('episode scope')
    native=read(ep/'native.json')
    if native['job']!=os.environ['SLURM_JOB_ID'] or native['step']!=os.environ['SLURM_STEP_ID']:raise ValueError('step identity')
    observed=native_identity();minor,uid=resolve_native(observed)
    if [uid]!=native['gpu_uuids']:raise ValueError('GPU identity')
    cache=subprocess.check_output(['/sbin/ldconfig','-p'],text=True,timeout=10)
    final,gate=rewrite(args,minor=minor,uuid=uid,libraries=driver_binds(cache),vendors=R/'opencl-vendors')
    env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
    p=subprocess.run(gate,env=env,capture_output=True,text=True,timeout=25)
    rows=[json.loads(v.removeprefix('ALLOWLIST_GATE ')) for v in p.stdout.splitlines() if v.startswith('ALLOWLIST_GATE ')]
    if p.returncode or len(rows)!=1 or rows[0].get('exact_device_namespace') is not True:raise ValueError('namespace gate')
    write(ep/f'binding-{os.getpid()}.json',dict(native_identity=observed,namespace=rows[0],system_bindpaths_disabled=True))
    os.execve(REAL_SINGULARITY,final,env)


def gpu_sample(gpu):
    p=subprocess.run(['nvidia-smi','-i',gpu,'--query-gpu=uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4)
    if p.returncode:raise ValueError('GPU telemetry missing')
    fields=next(csv.reader(p.stdout.splitlines()))
    if fields[0].strip()!=gpu:raise ValueError('GPU telemetry scope')
    p=subprocess.run(['nvidia-smi','-i',gpu,'--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=4)
    if p.returncode:raise ValueError('GPU clients missing')
    apps=[]
    for f in csv.reader(p.stdout.splitlines()):
        if not f:continue
        if f[0].strip()!=gpu:raise ValueError('client scope')
        apps.append(dict(pid=int(f[1]),memory_mib=float(f[2])))
    return dict(time=time.time(),memory_mib=float(fields[1]),utilization=float(fields[2]),apps=apps)


def output_structure(path,query):
    with path.open(newline='') as f:reader=csv.reader(f);head=next(reader);rows=list(reader)
    with Path(query).open(newline='') as f:q=list(csv.reader(f))
    if len(rows)!=len(q)-1 or len(head)<2 or len(set(head))!=len(head):raise ValueError('output shape')
    if len({r[0] for r in rows})!=len(rows) or {r[0] for r in rows}!={r[0] for r in q[1:]}:raise ValueError('query identity mismatch')
    for row in rows:
        if len(row)!=len(head) or any(not math.isfinite(float(v)) for v in row[1:]):raise ValueError('nonfinite output')
    return dict(rows=len(rows),columns=len(head),sha256=sha(path))


WARMUP='''import json,sys,inspect,random
from pathlib import Path
import numpy as np,torch,xgboost,catboost,lightgbm,sklearn
assert torch.cuda.is_available() and torch.cuda.device_count()==1
random.seed(130701);np.random.seed(130701);torch.manual_seed(130701)
a=torch.ones((128,128),device='cuda');b=a@a;torch.cuda.synchronize();assert b[0,0].item()==128
from catboost.utils import get_gpu_device_count
assert get_gpu_device_count()==1
Path('environment.json').write_text(json.dumps(dict(python=sys.version,torch=torch.__version__,cuda=torch.version.cuda,xgboost=xgboost.__version__,catboost=catboost.__version__,lightgbm=lightgbm.__version__,sklearn=sklearn.__version__,xgb_fit_parameters=list(inspect.signature(xgboost.XGBClassifier.fit).parameters),gpu_name=torch.cuda.get_device_name(0))))
'''

GPU_INSTRUMENT='''import json as _rjson, functools as _rfunctools
import xgboost as _rxgb, catboost as _rcat
_r14_gpu_receipts=[]
def _r14_track(_cls,_backend):
    _original=_cls.fit
    @_rfunctools.wraps(_original)
    def _tracked(self,*args,**kwargs):
        _result=_original(self,*args,**kwargs)
        if _backend=='xgboost':
            _booster=self.get_booster();_conf=_rjson.loads(_booster.save_config())
            _record=dict(backend=_backend,device=_conf['learner']['generic_param']['device'],rounds=_booster.num_boosted_rounds())
        else:_record=dict(backend=_backend,device=self.get_all_params().get('task_type'),rounds=self.tree_count_)
        _r14_gpu_receipts.append(_record)
        return _result
    _cls.fit=_tracked
_r14_track(_rxgb.XGBClassifier,'xgboost');_r14_track(_rcat.CatBoostClassifier,'catboost')
'''

GPU_RECEIPT='''import json as _rjson
from pathlib import Path as _RPath
assert _r14_gpu_receipts and all(str(r['device']).lower().startswith(('cuda','gpu')) and r['rounds']>0 for r in _r14_gpu_receipts)
_RPath('gpu_training.json').write_text(_rjson.dumps(_r14_gpu_receipts,sort_keys=True))
'''


def worker(index):
    p=read(R/'plan.json');m=runtime();ep=R/f'episode-{index}'
    row=schedule()[index] if index<36 else dict(index=36,arm='warmup',seed=SEED)
    source=p['programs'][row['program']] if index<36 else None
    gpu=m.infra().native_uuids(1)[0]
    os.environ.update(DOJO_GPU_UUIDS=gpu,POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),PATH=str(R/'bin')+':'+os.environ['PATH'])
    from dojo.main_local_worker import _process_start_ticks,_host_boot_id
    from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
    from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
    from dojo.utils.config import build
    from dojo.utils.experiment_deadline import ExperimentDeadline
    import dojo.core.interpreters.jupyter.jupyter_interpreter as ji
    # One shared Slurm step, DISTINCT local service endpoints, both arms identical.
    ji._slurm_gateway_port=lambda:31000+(int(os.environ['SLURM_JOB_ID'])%400)*40+index
    write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=[gpu]))
    write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=[gpu],container_pid=None,container_process_start_ticks=None))
    cfg=JupyterInterpreterConfig(working_dir=str(ep/'work'),timeout=120,container_runtime='singularity',superimage_directory=str(m.TASK_IMAGE.parent),superimage_version='2026-07-macos-v1',read_only_binds={source['data']:'/workspace/workspace_input'} if source else {},env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':str(CPU),'OPENBLAS_NUM_THREADS':str(CPU),'MKL_NUM_THREADS':str(CPU),'PYTHONHASHSEED':str(SEED)})
    interp=None;error=None;metrics={};start=time.time()
    write(ep/'started.json',dict(**row,start=start,affinity=sorted(os.sched_getaffinity(0))))
    try:
        with ExperimentDeadline(150).activate():
            interp=build(cfg,INTERPRETER_MAP,data_dir=source['data'] if source else R/'empty-data')
            code=(R/f'programs/{row["program"]}.py').read_text() if source else WARMUP
            if source:
                seed_setup='import random,numpy as np\nrandom.seed(130701);np.random.seed(130701)\n'
                setup=interp.run(seed_setup+(GPU_INSTRUMENT if source['expected_gpu'] else ''))
                if setup.exit_code or setup.timed_out:raise ValueError('seed/instrumentation prelude failed')
            write(ep/'candidate_started.json',dict(time=time.time()))
            out=interp.run(code,reset_session=source is None)
            write(ep/'candidate_ended.json',dict(time=time.time()))
            metrics.update(exit_code=out.exit_code,timed_out=out.timed_out,exec_seconds=out.exec_time)
            # Source/output text stays private and is never streamed to the agent/Git.
            (ep/'execution.private.txt').write_text('\n'.join(out.term_out))
            if out.exit_code or out.timed_out:raise RuntimeError('candidate execution failed')
            name='submission.csv' if source else 'environment.json'
            if not interp.fetch_file(ep/'work'/name):raise ValueError('missing output')
            metrics['output']=output_structure(ep/'work'/name,Path(source['data'])/'test.csv') if source else read(ep/'work'/name)
            if source and source['expected_gpu']:
                receipt=interp.run(GPU_RECEIPT,reset_session=False)
                if receipt.exit_code or receipt.timed_out or not interp.fetch_file(ep/'work/gpu_training.json'):raise ValueError('actual GPU training receipt absent')
                metrics['gpu_training']=read(ep/'work/gpu_training.json')
    except Exception as exc:error=type(exc).__name__
    finally:
        if interp is not None:
            try:interp.close()
            except Exception as exc:error=error or type(exc).__name__
        write(ep/'completed.json',dict(**row,**metrics,error_type=error,complete=error is None,start=start,end=time.time(),source_commit=p['source_commit']))
    return 0 if error is None else 1


def terminate_owned(process,ep):
    # The server starts a separate session: kill only the pinned live identity.
    from dojo.main_local_worker import _process_start_ticks
    if (ep/'identity.json').exists():
        identity=read(ep/'identity.json');pid=identity.get('container_pid');ticks=identity.get('container_process_start_ticks')
        if pid and ticks and _process_start_ticks(pid)==ticks and os.getpgid(pid)==identity.get('container_pgid'):
            os.killpg(os.getpgid(pid),signal.SIGTERM)
            time.sleep(1)
            if _process_start_ticks(pid)==ticks:os.killpg(os.getpgid(pid),signal.SIGKILL)
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)


def run_one(index):
    ep=R/f'episode-{index}';start=time.time()
    with (ep/'worker.private.log').open('xb') as f:
        process=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(index)],stdout=f,stderr=f,start_new_session=True)
        try:rc=process.wait(timeout=180)
        except subprocess.TimeoutExpired:terminate_owned(process,ep);rc=124
    write(ep/'closed.json',dict(returncode=rc,start=start,end=time.time()))
    return dict(index=index,returncode=rc,complete=rc==0 and (ep/'completed.json').exists() and read(ep/'completed.json')['complete'])


def controller():
    p=check();m=runtime();started=time.time()
    for _ in range(40):
        if (R/'launch.json').exists():break
        time.sleep(.25)
    if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!=p['node']:raise ValueError('allocation identity')
    gpu=m.infra().native_uuids(1)[0]
    if gpu_sample(gpu)['apps']:raise ValueError('unexpected baseline clients')
    write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuid=gpu,start=started,affinity=sorted(os.sched_getaffinity(0)),source_commit=p['source_commit']))
    attempted=[];blocks=[];error=None
    try:
        warm=run_one(36)
        if not warm['complete'] or gpu_sample(gpu)['apps']:raise ValueError('environment qualification failed')
        for block in range(6):
            rows=schedule()[6*block:6*block+6];width=1 if rows[0]['arm']=='serial' else 2
            if time.time()-started+math.ceil(6/width)*185>5250:raise TimeoutError('insufficient allocation budget for whole block')
            if gpu_sample(gpu)['apps']:raise ValueError('residual clients before block')
            samples=[];stop=threading.Event();telemetry_errors=[]
            def observe():
                while not stop.is_set():
                    try:samples.append(gpu_sample(gpu))
                    except Exception as exc:telemetry_errors.append(type(exc).__name__);break
                    stop.wait(.5)
            observer=threading.Thread(target=observe,daemon=True);start=time.time();observer.start()
            with concurrent.futures.ThreadPoolExecutor(max_workers=width) as pool:
                outcomes=list(pool.map(run_one,[r['index'] for r in rows]))
            stop.set();observer.join(timeout=10);attempted.extend(outcomes)
            entry=dict(block=block,arm=rows[0]['arm'],repeat=rows[0]['repeat'],width=width,start=start,end=time.time(),outcomes=outcomes,telemetry_errors=telemetry_errors)
            write(R/f'block-{block}.json',entry);write(R/f'telemetry-{block}.json',samples);blocks.append(entry)
            if telemetry_errors or observer.is_alive() or gpu_sample(gpu)['apps']:raise ValueError('telemetry/release gate failed')
            if not all(o['complete'] for o in outcomes):raise ValueError('fixed program qualification/execution failure; no replacement')
            if block==0:
                # Isolated first block: compute-client and nonzero utilization DURING each GPU candidate.
                for row in rows:
                    if not p['programs'][row['program']]['expected_gpu']:continue
                    t=read(R/f'episode-{row["index"]}/completed.json')
                    if not any(t['start']<=s['time']<=t['end'] and s['apps'] and s['utilization']>0 for s in samples):raise ValueError('actual GPU compute not observed')
    except Exception as exc:error=type(exc).__name__
    finally:
        full=[]
        for row in schedule():
            ep=R/f'episode-{row["index"]}';item=dict(**row,status='not_started',source_commit=p['source_commit'])
            if (ep/'started.json').exists():item['status']='incomplete'
            if (ep/'closed.json').exists():item.update(read(ep/'closed.json'));item['status']='failed'
            if (ep/'completed.json').exists():
                result=read(ep/'completed.json');item.update({k:v for k,v in result.items() if k!='output'});item['status']='complete' if result['complete'] and item.get('returncode')==0 else 'failed'
                item['output_sha256']=result.get('output',{}).get('sha256')
            full.append(item)
        write(R/'closed.json',dict(planned=36,attempted=sum(r['status']!='not_started' for r in full),completed=sum(r['status']=='complete' for r in full),error_type=error,elapsed_seconds=time.time()-started,source_commit=p['source_commit']))
        write(R/'runs.json',full)
        fields=sorted({k for r in full for k in r})
        with (R/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(full)
    return 1 if error else 0


def submit():
    check()
    if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
    env=runtime().infra().clean_env()
    jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
    if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
    write(R/'submit-intent.json',dict(approved_gpu_hours=1.5,plan_sha256=sha(R/'plan.json')))
    result=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
    job=result.stdout.strip().split(';')[0]
    if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
    write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
    print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=1.5)))


if __name__=='__main__':
    os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','submit','controller','worker']);ap.add_argument('--commit');ap.add_argument('--node',default='gpu27');ap.add_argument('--index',type=int);args=ap.parse_args()
    if args.mode=='prepare':prepare(args.commit,args.node)
    elif args.mode=='worker':sys.exit(worker(args.index))
    else:sys.exit(globals()[args.mode]())
