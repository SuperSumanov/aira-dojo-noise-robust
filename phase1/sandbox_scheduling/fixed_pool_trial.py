"""R14 small same-pool trial of SIMPLE admission baselines, not a novel method.

Four fixed programs / three tasks x three admission policies x three original-
seed restarts = 36 slots. New class-covered public input, never old-run rescue.
One 3090, six allocated CPUs, <=90min including failures, no API/quality scoring.
"""
import argparse
from collections import Counter
import concurrent.futures as cf
import copy
import csv
import functools
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time

import entry_recheck as entry
from lifecycle_pilot import sha, read, write

B=Path('/research/d7/spc/yzyang4')
D=B/'scheduling-entry-20261008-v2'
R=B/'scheduling-pool-20261008-v2'
PY=B/'venvs/aira/bin/python'
NAME='fixed_pool_trial.py'
DONOR_PLAN='6b68c0d0cb8526e375b5f5a2e1dec8f3ffaee0b035836b380c318272ba510762'
PROGRAMS=(0,1,4,3)
ARMS=('serial','share2','one_gpu')
CAP=5400


def schedule():
 rows=[]
 for repeat in range(3):
  order=[PROGRAMS[(j+repeat)%4] for j in range(4)]
  for arm in ARMS[repeat:]+ARMS[:repeat]:
   for program in order:
    rows.append(dict(index=len(rows),program=program,repeat=repeat,arm=arm,seed=130701))
 return rows


@functools.lru_cache(maxsize=1)
def configure():
 entry.R=R;entry.schedule=schedule
 return entry.pilot()


def choose(waiting, active, arm, gpu_programs):
 """Fixed FIFO except a blocked GPU head may be bypassed by CPU in one_gpu.

 No learned/LLM prediction. GPU flags are hand-checked source hints, fixed before
 execution. This is deliberately a strong cheap baseline, not semantic novelty.
 """
 width=1 if arm=='serial' else 2
 if len(active)>=width:return None
 gpu_active=any(r['program'] in gpu_programs for r in active)
 for row in waiting:
  if arm=='one_gpu' and gpu_active and row['program'] in gpu_programs:continue
  return row
 return None


def covered_fixture(old, output, minimum_counts=None):
 """Preserve old query; swap latest majority rows for first missing-class rows.

 Full source is hashed; only public-training rows, excluding every old query ID.
 Optional minima must cover each fold, not merely the unsplit training file.
 No duplication, relabeling, class-frequency resampling, or quality selection.
 """
 old_data=Path(old['programs'][0]['data'])
 with (old_data/'train.csv').open(newline='') as f:
  reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
 with (old_data/'test.csv').open(newline='') as f:query_ids={r['Id'] for r in csv.DictReader(f)}
 source=[p for p in old['public_inputs'] if p['path'].endswith('/tabular-playground-series-dec-2021/prepared/public/train.csv')]
 if len(source)!=1 or fields[-1]!='Cover_Type':raise ValueError('public source')
 original_ids={r['Id'] for r in rows}
 minimum_counts={} if minimum_counts is None else {str(k):int(v) for k,v in minimum_counts.items()}
 if any(v<1 for v in minimum_counts.values()):raise ValueError('positive class minima required')
 digest=hashlib.sha256();counts=Counter();first={};before=Path(source[0]['path']).stat()
 with Path(source[0]['path']).open('rb') as f:
  header=next(f);digest.update(header)
  if next(csv.reader([header.decode()]))!=fields:raise ValueError('source schema')
  for index,line in enumerate(f):
   digest.update(line)
   if b'"' in line:raise ValueError('numeric source assumption')
   values=line.decode().rstrip('\r\n').split(',');label=values[-1];counts[label]+=1
   picks=first.setdefault(label,[])
   if len(picks)<minimum_counts.get(label,1) and values[0] not in query_ids|original_ids:
    picks.append((index,dict(zip(fields,values))))
 after=Path(source[0]['path']).stat()
 if digest.hexdigest()!=source[0]['sha256'] or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('public source drift')
 present=Counter(r['Cover_Type'] for r in rows);replaced=[]
 if set(minimum_counts)-set(counts):raise ValueError('requested class absent from public source')
 minima={label:minimum_counts.get(label,1) for label in counts}
 for label in sorted(counts):
  needed=max(0,minima[label]-present[label])
  if len(first.get(label,[]))<needed:raise ValueError('missing class only present in excluded query or insufficient distinct public rows')
  for source_index,replacement in first[label][:needed]:
   available=[i for i,r in enumerate(rows) if present[r['Cover_Type']]>minima[r['Cover_Type']]]
   if not available:raise ValueError('class minima exceed fixture capacity')
   position=max(available);old_label=rows[position]['Cover_Type'];present[old_label]-=1;present[label]+=1
   rows[position]=replacement
   replaced.append(dict(position=position,public_source_index=source_index,old_class=old_label,new_class=label))
 if set(present)!=set(counts) or len({r['Id'] for r in rows})!=len(rows) or query_ids & {r['Id'] for r in rows}:raise ValueError('fixture coverage/disjointness')
 output.mkdir(mode=0o700,exist_ok=False)
 with (output/'train.csv').open('x',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
 for name in ('test.csv','sample_submission.csv'):shutil.copyfile(old_data/name,output/name)
 return dict(selection='replace latest surplus row with earliest distinct public row for prespecified class deficit; exclude all original/query IDs',
  training_rows=len(rows),query_rows=len(query_ids),replacements=replaced,class_counts=dict(present),
  minimum_counts=minima,
  public_source_sha256=digest.hexdigest(),unchanged_query=True,no_quality_labels_accessed=True,
  files={str(output/p.name):sha(p) for p in output.iterdir()})


def check():
 plan=read(R/'plan.json')
 if plan['schedule']!=schedule() or plan['gpu_hours_cap']!=1.5:raise ValueError('plan drift')
 for name,h in plan['files'].items():
  if sha(R/name)!=h:raise ValueError('source drift')
 for item in plan['public_inputs']:
  if sha(item['path'])!=item['sha256']:raise ValueError('input drift')
 return plan


def prepare(commit):
 import re
 if not re.fullmatch('[a-f0-9]{40}',commit) or sha(D/'plan.json')!=DONOR_PLAN:raise ValueError('source pin')
 if not (D/'closed.json').exists():raise ValueError('donor not closed')
 old=read(D/'plan.json');R.mkdir(mode=0o700,exist_ok=False)
 for name,h in old['files'].items():
  if name in ('run.sbatch','bin/singularity') or name.startswith('data-dec/'):continue
  if sha(D/name)!=h:raise ValueError('donor drift')
  dst=R/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(D/name,dst)
 for name in (NAME,'fixed_pool_readout.py','throughput_readout.py'):
  shutil.copyfile(Path(__file__).with_name(name),R/name)
 # Frozen source keeps its sole class-5 row in every training fold. Each other
 # class needs >=5 rows to select StratifiedKFold and stay in every training fold.
 fixture=covered_fixture(old,R/'data-dec',{str(k):(1 if k==5 else 5) for k in range(1,8)})
 from sklearn.model_selection import StratifiedKFold
 import numpy as np
 with (R/'data-dec/train.csv').open(newline='') as f:labels=np.array([int(r['Cover_Type']) for r in csv.DictReader(f)])
 non5=np.flatnonzero(labels!=5);rare5=np.flatnonzero(labels==5);fold_counts=[]
 for train,valid in StratifiedKFold(n_splits=5,shuffle=True,random_state=130701).split(non5,labels[non5]):
  counts=Counter(labels[np.concatenate([non5[train],rare5])].tolist())
  if set(counts)!=set(range(1,8)):raise ValueError('training fold missing class')
  fold_counts.append(dict(counts))
 fixture['fold_coverage_precheck']=dict(folds=5,all_training_classes_present=True,counts=fold_counts,
  limitation='class-support invariant under stratified seed; no model fit, not proof of full execution')
 write(R/'fixture.json',fixture)
 programs=copy.deepcopy(old['programs'])
 for p in programs:
  if p['task']=='tabular-playground-series-dec-2021':p['data']=str(R/'data-dec')
 for row in schedule()+[dict(index=36)]:(R/f'episode-{row["index"]}/work').mkdir(parents=True,exist_ok=True)
 (R/'empty-data').mkdir(exist_ok=True);(R/'bin').mkdir(exist_ok=True)
 (R/'bin/singularity').write_text(f'#!{PY}\nimport sys\nsys.path.insert(0,{str(R)!r})\nfrom fixed_pool_trial import configure\nconfigure().task_runtime()\n')
 os.chmod(R/'bin/singularity',0o700)
 batch=(D/'run.sbatch').read_text().replace('r14-entry-v2','r14-pool-v2').replace('00:15:00','01:30:00').replace('850s','5350s').replace(str(D),str(R)).replace('entry_recheck.py controller',f'{NAME} controller')
 (R/'run.sbatch').write_text(batch)
 inputs=old['public_inputs']+[dict(path=k,sha256=v) for k,v in fixture['files'].items()]
 plan=dict(source_commit=commit,donor_plan_sha256=DONOR_PLAN,schedule=schedule(),programs=programs,
  gpus=1,total_cpu=6,node='gpu27',allocation_seconds=CAP,gpu_hours_cap=1.5,planned_executions=36,
  candidate_timeout_seconds=120,worker_hard_seconds=180,seed=130701,public_inputs=inputs,
  source_changes=False,fixture_change='public per-fold class coverage, identical for every arm',
  previous_closed_batch='16992, 4 attempted/3 complete; not pooled into this trial',
  repeat_unit='same-seed restart, not independent training seed',order='Latin arm order, same rotated FIFO per repeat',
  arms=list(ARMS),gpu_source_hints=[0,4],hints_hand_checked_not_learned=True,
  first_serial_gate='all four complete including both actual GPU fits or stop entire trial',
  later_failure='retain failed slot, no retry; finish planned other arms if process release and telemetry gates pass',
  decision='exploratory: all own-arm blocks complete, median makespan improvement >=5%, no unexplained output drift; not semantic or E2E evidence',
  no_api=True,no_base_training=True,no_quality_scoring=True,
  files={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file()})
 write(R/'plan.json',plan);p=configure();m=p.runtime()
 from dojo.core.interpreters.base import ExecutionResult
 contract=entry.cell_receipt(ExecutionResult(term_out=[],exec_time=0.,exit_code=0),0,0,0)
 image_sha=sha(m.TASK_IMAGE)
 if image_sha!='801f646bed3cae6e74e10d793e71b0086658d4303d54552333c58125ddf9beda':raise ValueError('image drift')
 subprocess.run(['bash','-n',str(R/'run.sbatch')],check=True)
 write(R/'preflight.json',dict(plan_sha256=sha(R/'plan.json'),actual_result_contract=contract,image_sha256=image_sha,fixture_sha256=sha(R/'fixture.json'),candidate_executions=0))
 print(json.dumps(dict(status='PREPARED',root=str(R),plan_sha256=sha(R/'plan.json'),fixture=fixture)))


def run_one(index):
 p=configure();ep=R/f'episode-{index}';start=time.time()
 with (ep/'worker.private.log').open('xb') as f:
  proc=subprocess.Popen([str(PY),'-B',str(R/NAME),'worker','--index',str(index)],stdout=f,stderr=f,start_new_session=True)
  try:rc=proc.wait(timeout=180)
  except subprocess.TimeoutExpired:p.terminate_owned(proc,ep);rc=124
 write(ep/'closed.json',dict(returncode=rc,start=start,end=time.time()))
 return dict(index=index,returncode=rc,complete=rc==0 and (ep/'completed.json').exists() and read(ep/'completed.json')['complete'])


def execute_block(rows,arm):
 waiting=list(rows);active={};results=[];events=[]
 with cf.ThreadPoolExecutor(max_workers=2) as pool:
  while waiting or active:
   while (row:=choose(waiting,list(active.values()),arm,{0,4})) is not None:
    waiting.remove(row);events.append(dict(index=row['index'],program=row['program'],admitted=time.time()))
    active[pool.submit(run_one,row['index'])]=row
   if not active:raise ValueError('admission deadlock')
   done,_=cf.wait(active,return_when=cf.FIRST_COMPLETED)
   for future in done:results.append(future.result());del active[future]
 return sorted(results,key=lambda x:x['index']),events


def controller():
 plan=check();p=configure();m=p.runtime();started=time.time();error=None
 for _ in range(40):
  if (R/'launch.json').exists():break
  time.sleep(.25)
 if read(R/'launch.json')['job']!=os.environ['SLURM_JOB_ID'] or socket.gethostname().split('.')[0]!='gpu27':raise ValueError('allocation identity')
 gpu=m.infra().native_uuids(1)[0]
 write(R/'allocation.json',dict(job=os.environ['SLURM_JOB_ID'],gpu_uuid=gpu,start=started,affinity=sorted(os.sched_getaffinity(0))))
 try:
  if p.gpu_sample(gpu)['apps']:raise ValueError('unexpected GPU client')
  if not run_one(36)['complete'] or p.gpu_sample(gpu)['apps']:raise ValueError('environment qualification')
  for block in range(9):
   rows=schedule()[4*block:4*block+4];arm=rows[0]['arm']
   if time.time()-started+4*185>5250:raise TimeoutError('insufficient whole-block budget')
   if p.gpu_sample(gpu)['apps']:raise ValueError('residual GPU client')
   stop=threading.Event();samples=[];errors=[]
   def observe():
    while not stop.is_set():
     try:samples.append(p.gpu_sample(gpu))
     except Exception as exc:errors.append(type(exc).__name__);break
     stop.wait(.5)
   observer=threading.Thread(target=observe,daemon=True);start=time.time();observer.start()
   try:outcomes,events=execute_block(rows,arm)
   finally:stop.set();observer.join(timeout=10)
   write(R/f'block-{block}.json',dict(block=block,arm=arm,repeat=rows[0]['repeat'],start=start,end=time.time(),outcomes=outcomes,admission_events=events,telemetry_errors=errors))
   write(R/f'telemetry-{block}.json',samples)
   if errors or observer.is_alive() or p.gpu_sample(gpu)['apps']:raise ValueError('telemetry/release gate')
   if block==0:
    if not all(x['complete'] for x in outcomes):raise ValueError('first serial qualification failed')
    for row in rows:
     if row['program'] not in (0,4):continue
     done=read(R/f'episode-{row["index"]}/completed.json')
     if not done.get('gpu_training'):raise ValueError('actual GPU fit missing')
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
    item['gpu_training_verified']=bool(done.get('gpu_training'));item['output_sha256']=done.get('output',{}).get('sha256')
   full.append(item)
  write(R/'closed.json',dict(planned=36,attempted=sum(r['status']!='not_started' for r in full),complete=sum(r['status']=='complete' for r in full),controller_error=error,elapsed_seconds=time.time()-started))
  write(R/'runs.json',full)
  with (R/'runs.csv').open('x',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=sorted({k for r in full for k in r}));writer.writeheader();writer.writerows(full)
 return 1 if error or any(r['status']!='complete' for r in full) else 0


def submit():
 check()
 if read(R/'preflight.json')['plan_sha256']!=sha(R/'plan.json'):raise ValueError('preflight drift')
 env=configure().runtime().infra().clean_env()
 jobs=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i'],env=env,text=True,timeout=15).split()
 if set(jobs)-{'12535'}:raise ValueError('unexpected active job')
 write(R/'submit-intent.json',dict(gpu_hours_cap=1.5,planned=36,plan_sha256=sha(R/'plan.json')))
 proc=subprocess.run(['sbatch','--parsable','--chdir='+str(R),'--output='+str(R/'allocation-%j.out'),'--error='+str(R/'allocation-%j.err'),str(R/'run.sbatch')],env=env,capture_output=True,text=True,timeout=20)
 job=proc.stdout.strip().split(';')[0]
 if proc.returncode or not job.isdigit():raise RuntimeError('ambiguous submission; no retry')
 write(R/'launch.json',dict(job=job,plan_sha256=sha(R/'plan.json')))
 print(json.dumps(dict(status='SUBMITTED',job=job,gpu_hours_cap=1.5)))


if __name__=='__main__':
 os.umask(0o077);os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
 ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','submit','worker','controller']);ap.add_argument('--commit');ap.add_argument('--index',type=int);args=ap.parse_args()
 if args.mode=='prepare':prepare(args.commit)
 elif args.mode=='worker':configure();sys.exit(entry.worker(args.index))
 else:sys.exit(globals()[args.mode]())
