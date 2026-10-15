"""Closed pre-search failure evidence; no candidate/result data are read."""
import hashlib
import json
from pathlib import Path
import subprocess
from safe_senior_reader import redact

R=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261015-v1')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
launch=read(R/'launch.json');closed=read(R/'closed.json')
assert launch['job']=='18468' and closed['complete']==0
assert not any(R.glob('episode-*/deadline.json'))
raw=subprocess.check_output(['sacct','-j','18468','-X','-n','-P','-o','JobID,State,Start,End,ElapsedRaw,AllocGRES'],text=True)
entries=[x.split('|') for x in raw.strip().splitlines() if x]
assert len(entries)==1
j,state,start,end,elapsed,gres,*_=entries[0]
assert j=='18468' and state=='FAILED' and gres=='gpu:6'
cost=int(elapsed)*6
path=R/'block-0/executor.private.log'
safe,counts=redact(path.read_text())
cleanup=read(R/'block-0/service-cleanup.json')
out=dict(job=j,state=state,start_hk=start,end_hk=end,elapsed_seconds=int(elapsed),
    gpu_seconds=cost,gpu_hours=cost/3600,assigned=32,started=0,complete=0,
    source_commit=read(R/'plan.json')['source_commit'],plan_sha256=sha(R/'plan.json'),
    closed_sha256=sha(R/'closed.json'),executor_log_sha256=sha(path),
    error=closed['error'],executor_log_redacted=safe,redaction_counts=counts,
    service_cleanup_gpu_clean=cleanup['gpu_clean'],
    quality_claim=False,automatic_retry=False)
with (R/'failure-18468.safe.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
print(json.dumps(out,ensure_ascii=False,sort_keys=True))
