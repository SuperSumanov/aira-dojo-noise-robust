"""R14 fixed original neural programs: 2 tasks x 2 policies x 3 restarts.

No source/hyperparameter changes, official test, API, quality score or base LLM.
One RTX3090 / six CPUs / 90min all-in. First serial qualification or stop.
"""
import argparse
import ast
import concurrent.futures as cf
import csv
import functools
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import entry_recheck as entry
from entry_contract import setup_cell
from lifecycle_pilot import read,write,sha
from neural_inputs import make_cactus,make_denoising,files_manifest
from neural_instrument import INSTRUMENT,RECEIPT

B=Path('/research/d7/spc/yzyang4')
D=B/'scheduling-pool-20261008-v2'
R=B/'scheduling-neural-20261008-v1'
PY=B/'venvs/aira/bin/python'
NAME='neural_pool_trial.py'
SOURCE_PINS=(
 ('aerial-cactus-identification','c0888120b84c72f433712fb1c103f9e10e6ff18d84f5a15198d34b1159991369'),
 ('denoising-dirty-documents','0d7b2d191f2dd2e4dd7b28a6c3d678eb321eb3f008abdefab538703a71bbc3f9'))
IMAGE_SHA='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda'
CAP=5400

def schedule():
 rows=[]
 for repeat in range(3):
  for arm in (('serial','share2') if repeat%2==0 else ('share2','serial')):
   for program in ((0,1) if repeat%2==0 else (1,0)):
    rows.append(dict(index=len(rows),program=program,arm=arm,repeat=repeat,source_seed=42,harness_seed=130701))
 return rows

@functools.lru_cache(maxsize=1)
def pilot():
 entry.R=R;entry.schedule=schedule
 return entry.pilot()

def check():
 plan=read(R/'plan.json')
 if plan['schedule']!=schedule() or plan['gpu_hours_cap']!=1.5:raise ValueError('frozen plan')
 for name,h in plan['files'].items():
  if sha(R/name)!=h:raise ValueError('file drift')
 if os.readlink(R/'data-0/workspace_cache')!='/workspace/input_cache':raise ValueError('private cache drift')
 return plan

def prepare(commit):
 import census as c
 if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('exact commit')
 if sha(D/'plan.json')!='429339013cca8e2858cb2cc2edfefe017f096b0c4afbc0172987d897becf7a56' or not (D/'closed.json').exists():raise ValueError('donor')
 old=read(D/'plan.json');R.mkdir(mode=0o700,exist_ok=False)
 for name,h in old['files'].items():
  if not (name.startswith(('source/','forets_','opencl-vendors/')) or name in ('runtime.py','throughput_pilot.py','entry_recheck.py','entry_contract.py','lifecycle_pilot.py','census.py')):continue
  if sha(D/name)!=h:raise ValueError('donor drift')
  dest=R/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dest)
 for name in (NAME,'neural_inputs.py','neural_instrument.py','neural_pool_readout.py','throughput_readout.py'):
  shutil.copyfile(Path(__file__).with_name(name),R/name)
 selected=json.loads(c.read_pinned(c.SAMPLE,'11b3f7c9c28119b612f332af6b6ddfc6fabd02a4f7694912576e615871ed8039'))['selected']
 wanted=dict(SOURCE_PINS);found={}
 for filename,pin in c.PINS.items():
  rows=[r for r in selected if r['task'] in wanted and r['file']==filename]
  if not rows:continue
  obj=json.loads(c.read_pinned(c.ROOT/filename,pin))
  for row in rows:
   for code in c.get_pair(obj,row):
    if c.sha(code.encode())==wanted[row['task']]:found[row['task']]=code
  del obj
 if set(found)!=set(wanted):raise ValueError('fixed source missing')
 (R/'programs').mkdir();programs=[];fixtures=[]
 for i,(task,pin) in enumerate(SOURCE_PINS):
  raw=found[task].encode();pilot().code_safe(raw);(R/f'programs/{i}.py').write_bytes(raw)
  source=B/'mle-bench-data'/task/'prepared/public'
  fixture=(make_cactus if i==0 else make_denoising)(source,R/f'data-{i}')
  fixtures.append(dict(task=task,**fixture))
  programs.append(dict(task=task,source_sha256=pin,data=str(R/f'data-{i}'),expected_gpu=True))
 write(R/'fixtures.json',fixtures)
 for row in schedule()+[dict(index=36)]:
  ep=R/f'episode-{row["index"]}';(ep/'work/input_cache').mkdir(parents=True)
 (R/'empty-data').mkdir();(R/'bin').mkdir()
 (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom neural_pool_trial import pilot\npilot().task_runtime()\n')
 os.chmod(R/'bin/singularity',0o700)
 batch=(D/'run.sbatch').read_text().replace('r14-pool-v2','r14-neural-v1').replace(str(D),str(R)).replace('fixed_pool_trial.py controller',f'{NAME} controller')
 (R/'run.sbatch').write_text(batch)
 plan=dict(source_commit=commit,programs=programs,schedule=schedule(),node='gpu27',gpu_hours_cap=1.5,allocation_seconds=CAP,gpus=1,total_cpu=6,
  candidate_timeout=450,worker_hard_seconds=550,warmup_hard_seconds=180,planned_executions=12,
  first_serial_gate='both complete with nonzero CUDA Adam steps and valid output; otherwise stop without replacement',
  subsequent_failure='keep denominator; no retry; finish fixed arms only if release/isolation/telemetry safe',
  decision='all 12 complete; 3 full timing pairs; median speedup >=1.05; identical step counts per program; max cross-arm difference <=max within-arm difference+1e-6 and <=1e-5; not quality/E2E or new method',
  unchanged_source_and_hyperparameters=True,query_public_train_only=True,source_seed=42,harness_seed=130701,
  cache_contract='read-only fixture symlink points to empty private /workspace/input_cache per episode; no shared cache or precomputation',
  no_paid_api=True,no_base_model_update=True,no_official_test=True,no_quality_scores_read=True,
  fixture_scope='cactus all public training except first 64 IDs; denoising first 31 public pairs + next 2 noisy query, unmodified source internal 15-image validation',
  files=files_manifest(R))
 write(R/'plan.json',plan)
 m=pilot().runtime()
 if sha(m.TASK_IMAGE)!=IMAGE_SHA:raise ValueError('image drift')
 from forets_gpu_binding_20260911 import REAL_SINGULARITY
 # Import statements only, no candidate top-level statements or main function.
 preflight='''import ast,inspect,json,sys,torch,torchvision,numpy,pandas,scipy,sklearn
from pathlib import Path
assert not torch.cuda.is_available()
for i in (0,1):
 tree=ast.parse(Path(f'/r14/programs/{i}.py').read_text())
 imports=ast.Module(body=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom))],type_ignores=[])
 exec(compile(imports,'candidate_imports','exec'),{})
assert 'verbose' in inspect.signature(torch.optim.lr_scheduler.ReduceLROnPlateau).parameters
sys.path.insert(0,'/r14')
from neural_instrument import INSTRUMENT
def run(instrument):
 torch.manual_seed(42);model=torch.nn.Linear(2,1);opt=torch.optim.Adam(model.parameters(),lr=.01)
 if instrument:exec(INSTRUMENT,globals())
 for i in range(3):
  opt.zero_grad();model(torch.ones(2,2)).sum().backward();opt.step()
 return [p.detach().clone() for p in model.parameters()]
a=run(False);b=run(True)
assert all(torch.equal(x,y) for x,y in zip(a,b)) and len(_r14_steps)==3
print(json.dumps(dict(torch=torch.__version__,torchvision=torchvision.__version__,numpy=numpy.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,imports_pass=True,adam_instrument_cpu_equivalence=True,no_candidate_execution=True)))
'''
 (R/'dependency_check.py').write_text(preflight)
 env={k:os.environ[k] for k in ('PATH','HOME','USER','LOGNAME') if k in os.environ}
 cmd=[REAL_SINGULARITY,'exec','--containall','--cleanenv','--no-home','--no-mount','hostfs,bind-paths','--bind',str(R)+':/r14:ro','--pwd','/tmp',str(m.TASK_IMAGE),'python','/r14/dependency_check.py']
 result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120)
 if result.returncode:raise ValueError('CPU image dependency/instrument preflight failed: '+result.stderr[-800:])
 version=read_json_line(result.stdout)
 subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
 write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),image_sha256=IMAGE_SHA,dependency_check_sha256=sha(R/'dependency_check.py'),versions=version,
  matrix=12,gpu_executions=0,official_test_accessed=False,fixture_sha256=sha(R/'fixtures.json')))
 print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),versions=version)))

def read_json_line(text):
 lines=[v for v in text.splitlines() if v.startswith('{')]
 if len(lines)!=1:raise ValueError('unexpected dependency receipt')
 return json.loads(lines[0])

def worker(index):
 plan=read(R/'plan.json');p=pilot();m=p.runtime();ep=R/f'episode-{index}';warm=index==36
 row=dict(index=36,arm='warmup') if warm else schedule()[index]
 source=None if warm else plan['programs'][row['program']]
 gpu=m.infra().native_uuids(1)[0]
 os.environ.update(DOJO_GPU_UUIDS=gpu,POLICY9B_EPISODE=str(ep),DOJO_WORKER_IDENTITY_PATH=str(ep/'identity.json'),PATH=str(R/'bin')+':'+os.environ['PATH'])
 from dojo.main_local_worker import _process_start_ticks,_host_boot_id
 from dojo.config_dataclasses.interpreter.jupyter import JupyterInterpreterConfig
 from dojo.config_dataclasses.interpreter import INTERPRETER_MAP
 from dojo.utils.config import build
 from dojo.utils.experiment_deadline import ExperimentDeadline
 import dojo.core.interpreters.jupyter.jupyter_interpreter as ji
 ji._slurm_gateway_port=lambda:31000+(int(os.environ['SLURM_JOB_ID'])%400)*40+index
 write(ep/'native.json',dict(job=os.environ['SLURM_JOB_ID'],step=os.environ['SLURM_STEP_ID'],gpu_uuids=[gpu]))
 write(ep/'identity.json',dict(pid=os.getpid(),pgid=os.getpgid(0),process_start_ticks=_process_start_ticks(os.getpid()),host_boot_id=_host_boot_id(),gpu_uuids=[gpu],container_pid=None,container_process_start_ticks=None))
 cfg=JupyterInterpreterConfig(working_dir=str(ep/'work'),timeout=60 if warm else 450,container_runtime='singularity',superimage_directory=str(m.TASK_IMAGE.parent),superimage_version='2026-07-macos-v1',
  read_only_binds={source['data']:'/workspace/workspace_input'} if source else {},env={'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'6','OPENBLAS_NUM_THREADS':'6','MKL_NUM_THREADS':'6','PYTHONHASHSEED':'130701'})
 start=time.time();interp=None;metrics={};error=None;stage=0
 write(ep/'started.json',dict(**row,start=start,affinity=sorted(os.sched_getaffinity(0))))
 def invoke(code,**kw):
  nonlocal stage
  begin=time.time();n=stage;stage+=1;result=interp.run(code,**kw)
  write(ep/f'cell-{n}.json',entry.cell_receipt(result,n,begin,time.time()))
  (ep/f'cell-{n}.private.txt').write_text('\n'.join(map(str,result.term_out)))
  return result
 try:
  with ExperimentDeadline(120 if warm else 525).activate():
   interp=build(cfg,INTERPRETER_MAP,data_dir=source['data'] if source else R/'empty-data')
   if not warm:
    prelude=setup_cell(130701,INSTRUMENT)+"\nassert _r14_torch.cuda.is_available() and _r14_torch.cuda.device_count()==1\n"
    setup=invoke(prelude)
    if setup.exit_code or setup.timed_out:raise ValueError('prelude failed')
   write(ep/'candidate_started.json',dict(time=time.time()))
   result=invoke(p.WARMUP if warm else (R/f'programs/{row["program"]}.py').read_text(),reset_session=warm)
   write(ep/'candidate_ended.json',dict(time=time.time()))
   metrics.update(exit_code=result.exit_code,timed_out=result.timed_out,exec_seconds=result.exec_time)
   if result.exit_code or result.timed_out:raise RuntimeError('candidate failed')
   name='environment.json' if warm else 'submission.csv'
   if not interp.fetch_file(ep/'work'/name):raise ValueError('missing output')
   metrics['output']=read(ep/'work'/name) if warm else p.output_structure(ep/'work'/name,Path(source['data'])/'test.csv')
   if not warm:
    result=invoke(RECEIPT,reset_session=False)
    if result.exit_code or result.timed_out or not interp.fetch_file(ep/'work/gpu_training.json'):raise ValueError('GPU steps unverified')
    metrics['gpu_training']=read(ep/'work/gpu_training.json')
 except Exception as exc:error=type(exc).__name__
 finally:
  if interp is not None:
   try:interp.close()
   except Exception as exc:error=error or type(exc).__name__
  write(ep/'completed.json',dict(**row,**metrics,error_type=error,complete=error is None,start=start,end=time.time(),source_commit=plan['source_commit']))
 return 1 if error else 0

def run_one(index):
 ep=R/f'episode-{index}';start=time.time()
 with (ep/'worker.private.log').open('xb') as f:
  proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(index)],stdout=f,stderr=f,start_new_session=True)
  try:rc=proc.wait(timeout=180 if index==36 else 550)
  except subprocess.TimeoutExpired:pilot().terminate_owned(proc,ep);rc=124
 write(ep/'closed.json',dict(returncode=rc,start=start,end=time.time()))
 return dict(index=index,returncode=rc,complete=rc==0 and (ep/'completed.json').exists() and read(ep/'completed.json')['complete'])

def controller():
 plan=check();p=pilot();m=p.runtime();start=time.time();error=None
 for _ in range(40):
  if (R/'launch.json').exists():break
  time.sleep(.25)
 if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':raise ValueError('allocation identity')
 gpu=m.infra().native_uuids(1)[0]
 write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,start=start,affinity=sorted(os.sched_getaffinity(0))))
 try:
  if p.gpu_sample(gpu)['apps']:raise ValueError('baseline GPU client')
  if not run_one(36)['complete'] or p.gpu_sample(gpu)['apps']:raise ValueError('warmup/release')
  for block in range(6):
   rows=schedule()[2*block:2*block+2];arm=rows[0]['arm'];width=1 if arm=='serial' else 2
   if time.time()-start+math.ceil(2/width)*555>5290:raise TimeoutError('whole block budget')
   if p.gpu_sample(gpu)['apps']:raise ValueError('preblock release')
   stop=threading.Event();samples=[];errors=[]
   def observe():
    while not stop.is_set():
     try:samples.append(p.gpu_sample(gpu))
     except Exception as exc:errors.append(type(exc).__name__);break
     stop.wait(.5)
   observer=threading.Thread(target=observe,daemon=True);begin=time.time();observer.start()
   try:
    with cf.ThreadPoolExecutor(max_workers=width) as pool:outcomes=list(pool.map(run_one,[r['index'] for r in rows]))
   finally:stop.set();observer.join(timeout=10)
   write(R/f'block-{block}.json',dict(block=block,arm=arm,repeat=rows[0]['repeat'],start=begin,end=time.time(),outcomes=outcomes,telemetry_errors=errors))
   write(R/f'telemetry-{block}.json',samples)
   if errors or observer.is_alive() or p.gpu_sample(gpu)['apps']:raise ValueError('telemetry/release')
   if block==0 and not all(o['complete'] for o in outcomes):raise ValueError('first serial qualification failed')
 except Exception as exc:error=type(exc).__name__
 finally:
  full=[]
  for row in schedule():
   ep=R/f'episode-{row["index"]}';item=dict(**row,status='not_started',source_commit=plan['source_commit'])
   if (ep/'started.json').exists():item['status']='incomplete'
   if (ep/'closed.json').exists():item.update(read(ep/'closed.json'));item['status']='failed'
   if (ep/'completed.json').exists():
    done=read(ep/'completed.json');item.update({k:v for k,v in done.items() if k not in ('output','gpu_training')})
    item['status']='complete' if done['complete'] and item.get('returncode')==0 else 'failed'
    item['gpu_steps']=done.get('gpu_training',{}).get('steps');item['output_sha256']=done.get('output',{}).get('sha256')
   full.append(item)
  write(R/'closed.json',dict(planned=12,attempted=sum(r['status']!='not_started' for r in full),completed=sum(r['status']=='complete' for r in full),controller_error=error,elapsed_seconds=time.time()-start))
  write(R/'runs.json',full)
  with (R/'runs.csv').open('x',newline='') as f:
   w=csv.DictWriter(f,fieldnames=sorted({k for r in full for k in r}));w.writeheader();w.writerows(full)
 return 1 if error or any(r['status']!='complete' for r in full) else 0

def submit():
 check()
 if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
 env=pilot().runtime().infra().clean_env()
 jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
 if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
 write(R/'submit-intent.json',dict(gpu_hours_cap=1.5,planned=12,plan_sha256=sha(R/'plan.json')))
 result=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
 job=result.stdout.strip().split(';')[0]
 if result.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
 write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
 print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=1.5)))

if __name__=='__main__':
 os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','worker','controller']);ap.add_argument('--commit');ap.add_argument('--index',type=int);args=ap.parse_args()
 if args.mode=='prepare':prepare(args.commit)
 elif args.mode=='worker':sys.exit(worker(args.index))
 else:sys.exit(globals()[args.mode]())
