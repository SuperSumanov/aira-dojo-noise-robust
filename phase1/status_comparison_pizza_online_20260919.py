"""Structure-only status, no outcomes or candidate data."""
import json,os,subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-pizza-full-deadline-20260919-yaywhbo1')
job=json.loads((ROOT/'launch.json').read_bytes())['job']
raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
allocation,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
out=dict(job=job,allocation=allocation,services_ready=(ROOT/'services-ready.json').exists(),closed=(ROOT/'closed.json').exists(),episodes=[])
for i in range(4):
    ep=ROOT/f'episode-{i}'
    out['episodes'].append(dict(index=i,started=(ep/'start.json').exists(),finished=(ep/'finished.json').exists(),generation_files=len(list(ep.glob('generation-*.private.json'))),action_files=len(list(ep.glob('action-*.json')))))
if out['closed']:out['closed_status']=json.loads((ROOT/'closed.json').read_bytes())['status']
print(json.dumps(out))
