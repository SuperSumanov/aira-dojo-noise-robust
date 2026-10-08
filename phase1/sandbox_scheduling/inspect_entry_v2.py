"""Only fixed entry-diagnostic metadata and error categories; no log contents."""
import argparse
import json
import re
from pathlib import Path
from lifecycle_pilot import read, sha, SECRET

ap=argparse.ArgumentParser()
ap.add_argument('--batch',choices=('entry-v2','pool-v1','pool-v2'),default='entry-v2')
args=ap.parse_args()
R=Path('/research/d7/spc/yzyang4')/dict(
 **{'entry-v2':'scheduling-entry-20261008-v2','pool-v1':'scheduling-pool-20261008-v1','pool-v2':'scheduling-pool-20261008-v2'})[args.batch]
CATEGORIES={
 'gpu_hist_removed':r'Invalid Input:.*gpu_hist',
 'invalid_classes':r'Invalid classes inferred',
 'early_stopping_fit_argument':r"unexpected keyword argument.*early_stopping_rounds",
 'eval_metric_fit_argument':r"unexpected keyword argument.*eval_metric",
 'cuda_unavailable':r'No visible GPU|Must have at least one device|not compiled with GPU support|CUDA driver version is insufficient',
 'xgb_parameter_validation':r'Invalid Parameter|Invalid Input|Unknown tree method',
 'memory_error':r'out of memory|bad_alloc|MemoryError',
 'feature_type':r'DataFrame.dtypes|could not convert string',
}
rows=[]
for index in {'entry-v2':(0,1),'pool-v1':(0,1,2,3),'pool-v2':(17,)}[args.batch]:
 ep=R/f'episode-{index}'; files=[]
 for name in ('cell-0.private.txt','cell-1.private.txt','cell-2.private.txt','worker.private.log'):
  p=ep/name
  if not p.exists():continue
  raw=p.read_bytes()
  if SECRET.search(raw):raise ValueError('credential-shaped log withheld')
  text=re.sub(r'\x1b\[[0-9;]*m','',raw.decode(errors='replace'))
  errors=[]
  for line in text.splitlines():
   if re.match(r'^(?:RuntimeError|ValueError|TypeError|XGBoostError):',line.strip()):
    message=re.sub(r'(?:/[A-Za-z0-9_.-]+){2,}','[path]',line.strip())
    message=re.sub(r'\d+(?:\.\d+)?','#',message)
    errors.append(message[:240])
  files.append(dict(name=name,sha256=sha(p),bytes=len(raw),
   sanitized_runtime_errors=errors,
   exception_types=sorted(set(re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*(?:Error|Exception)):',text))),
   categories={k:bool(re.search(v,text,re.I)) for k,v in CATEGORIES.items()}))
 done=read(ep/'completed.json')
 rows.append(dict(index=index,candidate_started=(ep/'candidate_started.json').exists(),
  complete=done['complete'],exit_code=done.get('exit_code'),exec_seconds=done.get('exec_seconds'),
  gpu_training=done.get('gpu_training'),files=files))
out=dict(job=read(R/'launch.json')['job'],plan_sha256=sha(R/'plan.json'),
 closed_sha256=sha(R/'closed.json'),runs_sha256=sha(R/'runs.json'),rows=rows,
 raw_logs_exported=False,score_fields_accessed=False)
print(json.dumps(out,sort_keys=True))
