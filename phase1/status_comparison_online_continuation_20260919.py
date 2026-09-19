"""Structural progress only; never read live answers, scores, or incumbents."""
import json,os,subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-online-continuation-20260919-qpw9ys94')
job=json.loads((ROOT/'launch.json').read_bytes())['job']
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
allocation,=[r.split('|') for r in raw.splitlines() if r.split('|')[0]==job]
out=dict(job=job,allocation=allocation,services_ready=(ROOT/'services-ready.json').exists(),closed=(ROOT/'closed.json').exists(),episodes=[])
for index in range(4):
    ep=ROOT/f'episode-{index}'
    out['episodes'].append(dict(index=index,started=(ep/'start.json').exists(),finished=(ep/'finished.json').exists(),
        generation_files=len(list(ep.glob('generation-*.private.json'))),action_files=len(list(ep.glob('action-*.json')))))
if out['closed']:out['closed_status']=json.loads((ROOT/'closed.json').read_bytes())['status']
print(json.dumps(out))
