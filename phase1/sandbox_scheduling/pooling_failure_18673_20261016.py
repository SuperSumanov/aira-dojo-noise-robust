"""Closed startup failure: redact remotely before exposing its short trace."""
import hashlib
import json
from pathlib import Path
import subprocess
from safe_senior_reader import redact

root=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261016-v2')
read=lambda p:json.loads(p.read_text())
assert read(root/'launch.json')['job']=='18673'
closed=read(root/'closed.json')
assert closed['planned']==32 and closed['complete']==0 and closed['attempted_blocks']==[]
raw=subprocess.check_output(['sacct','-j','18673','-X','-n','-P','-o','JobID,State,Start,End,ElapsedRaw,AllocGRES'],text=True)
rows=[x.split('|') for x in raw.splitlines() if x]
assert len(rows)==1
job,state,start,end,elapsed,gres,*_=rows[0]
assert job=='18673' and state=='FAILED' and gres=='gpu:6'
path=root/'block-0/service.private.log'
safe,counts=redact(path.read_text())
assert len(safe)<4096
out=dict(job=job,state=state,start_hk=start,end_hk=end,elapsed_seconds=int(elapsed),
    gpu_seconds=int(elapsed)*6,gpu_hours=int(elapsed)*6/3600,assigned=32,started=0,complete=0,
    source_commit=read(root/'plan.json')['source_commit'],
    plan_sha256=hashlib.sha256((root/'plan.json').read_bytes()).hexdigest(),
    service_cleanup=read(root/'block-0/service-cleanup.json'),
    service_trace_redacted=safe,redaction_counts=counts,
    service_log_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    quality_claim=False,automatic_retry=False)
with (root/'failure-18673.safe.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
print(json.dumps(out,sort_keys=True))
