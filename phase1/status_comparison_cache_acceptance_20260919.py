"""Read only allocation/closure metadata, never model analysis values."""
import json,os,subprocess
from pathlib import Path
root=Path('/research/d7/spc/yzyang4/comparison-cache-acceptance-20260919-tsefctlz')
job=json.loads((root/'launch.json').read_text())['job']
if job!='14136':raise ValueError('unexpected allocation')
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
allocation,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
print(json.dumps(dict(job=job,allocation=allocation,ready=(root/'ready.json').exists(),
                     analysis_records=sum((root/f'analysis-{i}.json').exists() for i in range(8)),
                     closed=(root/'closed.json').exists())))
