"""Cancel only our identified, still-pending gpu28 allocation; never running work."""
import json,os,subprocess,time
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-v1')
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
assert json.loads((R/'launch.json').read_bytes())['job']=='15336'
row=subprocess.check_output(['squeue','-j','15336','-h','-o','%i,%u,%T,%M'],env=env,text=True,timeout=20).strip()
assert row=='15336,yzyang4,PENDING,0:00', 'Do not migrate an allocation that may have started'
assert not (R/'claim.json').exists() and not (R/'service-native.json').exists()
# The scheduler's pending-only filter closes the read/cancel race.
subprocess.run(['scancel','--state=PENDING','15336'],env=env,check=True,timeout=25)
for _ in range(10):
    if not subprocess.check_output(['squeue','-j','15336','-h','-o','%T'],env=env,text=True,timeout=20).strip():break
    time.sleep(1)
else:raise RuntimeError('pending cancellation unconfirmed; no replacement submission')
raw=subprocess.check_output(['sacct','-X','-j','15336','-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=env,text=True,timeout=25)
f=next(z.split('|') for z in raw.splitlines() if z.split('|')[0]=='15336')
assert f[1].startswith('CANCELLED') and int(f[2])==0 and not (R/'claim.json').exists()
receipt=dict(job='15336',state=f[1],elapsed_seconds=0,gpu_hours=0,reason='gpu28 8/9 GPUs occupied by a 72h allocation; migrate whole matrix to same-model gpu1 under unchanged total cap',planned_successor='automatic-specification-20261003-gpu1-v2')
with (R/'cancelled-pending.json').open('x') as stream:json.dump(receipt,stream,sort_keys=True,indent=2)
print(json.dumps(receipt))
