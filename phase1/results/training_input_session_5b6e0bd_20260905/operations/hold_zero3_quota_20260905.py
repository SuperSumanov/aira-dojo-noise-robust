import json, os, subprocess, tempfile, datetime
from pathlib import Path
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
root=Path(tempfile.mkdtemp(prefix='zero3-quota-incident-'))
def call(args):
    return subprocess.check_output(args,env=env,timeout=25,text=True)
raw=call(['scontrol','show','job','-o','12510'])
(root/'before.txt').write_text(raw)
d=dict(x.split('=',1) for x in raw.split() if '=' in x)
assert d['UserId'].startswith('yzyang4(')
assert d['JobName']=='critic_zero3_resume'
assert d['Command']=='/research/d7/spc/yzyang4/worktrees/zero3-engineering-d22a17f3f6e6/phase1/scripts/zero3_session_engineering_20260905.sbatch'
assert d['Requeue']==d['Restarts']=='0'
assert d['JobState']=='PENDING', 'Do not mutate running or terminal job'
(root/'HOLD_INTENT.json').write_text(json.dumps({'job':12510,'reason':'research disk EDQUOT during metadata receipt write','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
subprocess.run(['scontrol','hold','12510'],env=env,check=True,timeout=25)
raw2=call(['scontrol','show','job','-o','12510'])
(root/'after.txt').write_text(raw2)
d2=dict(x.split('=',1) for x in raw2.split() if '=' in x)
assert d2['JobState']=='PENDING' and d2['Reason']=='JobHeldUser'
print(json.dumps({'incident':str(root),'job':12510,'state':d2['JobState'],'reason':d2['Reason'],'runtime':d2['RunTime']}))
