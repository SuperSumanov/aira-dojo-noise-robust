import hashlib,json,os,subprocess
from pathlib import Path
base=Path('/research/d7/spc/yzyang4');root=base/'critic-pivot-shape/submission-20260906-capacity-recovered'
commit='50f2967ad2637850742075454440aea2c5fa8a28';control=base/'worktrees/critic-pivot-shape-50f2967ad263'
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
def run(cmd):return subprocess.check_output(list(map(str,cmd)),env=env,timeout=30)
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=read(root/'READY.json');submitted=read(root/'SUBMITTED.json');jid=submitted['job_id']
assert jid.isdigit() and jid!='12535' and submitted['commit']==commit
assert r['commit']==commit and r['control']==str(control) and r['gpu_seconds_upper_bound']==3840
assert run(['git','-C',control,'rev-parse','HEAD']).decode().strip()==commit
assert not run(['git','-C',control,'status','--porcelain','--untracked-files=all']).strip()
for name,h in r['hashes'].items():
    assert sha(control/name)==h==hashlib.sha256(run(['git','-C',control,'show',commit+':'+name])).hexdigest()
for name,h in r['evidence_hashes'].items():assert sha(root/name)==h
space=read(root/'space-probe.json');released=read(root/'space-probe-released.json')
assert space['passed'] is True and space['requested_bytes']==68719476736 and space['allocated_bytes']>=68719476736
assert released['own_inode_removed'] is True and (released['device'],released['inode'])==(space['device'],space['inode'])
assert not (root/'own-checkpoint-space-probe.bin').exists()
a=read(control/'phase1/manifests/pivot_zero3_shape_approval_20260906.json')
assert a['pretrained_critic_weights_allowed'] is True and a['agent_base_update_allowed'] is False
assert a['automatic_retries']==0 and a['source_admission'] is False and a['real_corpus_reads']==0
assert sha(base/'critic-zero3-engineering/job-12575/TERMINAL_VERIFIED.json')==a['tiny_terminal_sha256']=='14dae4dbc7e1497695d1081517a1603833f4a6f97bd8ac3d534b5e0debdffaa2'
q=run(['squeue','-h','-u','yzyang4','-o','%i']).decode().split();assert len(q)==2 and set(q)=={'12535',jid}
f=dict(x.split('=',1) for x in run(['scontrol','show','job','-o',jid]).decode().split() if '=' in x)
expected={'JobId':jid,'JobState':'PENDING','Reason':'JobHeldUser','RunTime':'00:00:00','TimeLimit':'00:26:00',
    'Requeue':'0','Restarts':'0','NumCPUs':'12','CPUs/Task':'12','MinMemoryNode':'0','NumTasks':'1',
    'ReqNodeList':'projgpu39','Partition':'gpu_24h','QOS':'gpu','TresPerNode':'gpu:pro6000:2',
    'Command':str(control/'phase1/scripts/pivot_zero3_shape_20260906.sbatch'),'WorkDir':str(control)}
assert all(f.get(k)==v for k,v in expected.items()) and f['UserId'].startswith('yzyang4(')
assert f['NumNodes'] in ('1','1-1') and {'cpu=12','gres/gpu=2','node=1'}.issubset(f['TRES'].split(','))
old=dict(x.split('=',1) for x in run(['scontrol','show','job','-o','12535']).decode().split() if '=' in x)
assert all(old.get(k)==v for k,v in {'JobState':'PENDING','Reason':'JobHeldUser','RunTime':'00:00:00',
    'TresPerNode':'gpu:pro6000:2','ReqNodeList':'projgpu39','TimeLimit':'00:26:00','Requeue':'0'}.items())
rows=run(['sacct','-X','-n','-P','-j','12181,12288,12377,12486,12497,12499,12510,12570,12571,12572,12573,12574,12575',
    '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode']).decode().splitlines()
assert len(rows)==13
total=0;seen=set()
for row in rows:
    j,state,seconds,tres,rc=row.split('|')[:5];assert j not in seen;seen.add(j)
    assert state in ('COMPLETED','FAILED') and seconds.isdigit()
    fields=dict(x.split('=',1) for x in tres.split(','));total+=int(seconds)*int(fields['gres/gpu'])
assert total==7006 and total+3840==10846<=14400
result={'status':'INDEPENDENT_HELD_PRE_RELEASE_VERIFIED','job_id':jid,'source_commit':commit,
    'source_files_verified':len(r['hashes']),'fields':expected,'original_12535_unchanged':True,
    'actual_space_probe_bytes':68719476736,'maximum_new_job_gpu_seconds':3840,'enumerated_prior_actual_gpu_seconds':total,
    'enumerated_combined_upper_bound_gpu_seconds':10846,'inspector_sha256':sha(Path(__file__))}
with (root/'INDEPENDENT_PRE_RELEASE.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
print(json.dumps(result,sort_keys=True))
