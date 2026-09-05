import json,os,subprocess
from pathlib import Path
root=Path('/research/d7/spc/yzyang4/critic-zero3-engineering/node-metadata')
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
with (root/'SUBMISSION_INTENT.json').open('x') as f:json.dump({'gpus':0,'max_jobs':1,'seconds':120},f)
cmd=['sbatch','--parsable','--hold',str(root/'check.sbatch')]
p=subprocess.run(cmd,env=env,capture_output=True,timeout=40)
(root/'sbatch.stdout').write_bytes(p.stdout);(root/'sbatch.stderr').write_bytes(p.stderr)
assert p.returncode==0
jid=p.stdout.decode().strip().split(';')[0];assert jid.isdigit()
(root/'SUBMITTED.json').write_text(json.dumps({'job':jid}))
raw=subprocess.check_output(['scontrol','show','job','-o',jid],env=env).decode()
fields=dict(x.split('=',1) for x in raw.split() if '=' in x)
assert fields['JobState']=='PENDING' and fields['Reason']=='JobHeldUser'
assert fields['NumCPUs']=='1' and fields['ReqNodeList']=='gpu28' and fields['TimeLimit']=='00:02:00'
assert 'gres/gpu' not in fields.get('TRES','') and 'gpu' not in fields.get('TresPerNode','')
assert fields['Requeue']==fields['Restarts']=='0'
(root/'VERIFIED_HELD.json').write_text(json.dumps(fields,sort_keys=True,indent=2))
subprocess.run(['scontrol','release',jid],env=env,check=True,timeout=20)
print(json.dumps({'job':jid,'status':'RELEASED_CPU_ONLY','gpu_requested':0}))
