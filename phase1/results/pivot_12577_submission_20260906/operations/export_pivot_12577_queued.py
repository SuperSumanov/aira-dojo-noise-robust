import datetime,hashlib,json,os,re,subprocess,tarfile
from pathlib import Path
base=Path('/research/d7/spc/yzyang4')
root=base/'critic-pivot-shape/submission-20260906-capacity-recovered'
commit='50f2967ad2637850742075454440aea2c5fa8a28'
shape=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def read(path):
 assert path.is_file() and not path.is_symlink() and path.stat().st_uid==os.getuid()
 raw=path.read_bytes();assert len(raw)<1048576 and not shape.search(raw)
 return raw
def obj(path):return json.loads(read(path))
def sha(path):return hashlib.sha256(read(path)).hexdigest()
ready=obj(root/'READY.json');assert ready['commit']==commit
control=Path(ready['control'])
assert all(sha(control/n)==h for n,h in ready['hashes'].items())
assert all(sha(root/n)==h for n,h in ready['evidence_hashes'].items())
assert obj(root/'RELEASED.json')=={'commit':commit,'job_id':'12577'}
assert obj(root/'INDEPENDENT_PRE_RELEASE.json')['source_commit']==commit
names=['prepare_intent.json','PREVIOUS_CAPACITY_FAILURE.json','READY.json','cpu-tests.log','runtime-plan.json',
 'runtime-plan.log','space-probe.json','space-probe-released.json','SUBMISSION_INTENT.json','SUBMITTED.json',
 'VERIFIED_HELD.json','RELEASED.json','INDEPENDENT_PRE_RELEASE.json','command.json','sbatch.stdout','sbatch.stderr','sbatch_status.json']
out=Path('/tmp/pivot-12577-queued-receipts');assert not out.exists();out.mkdir(mode=0o700)
manifest={}
for n in names:
 raw=read(root/n)
 with (out/n).open('xb') as f:f.write(raw)
 manifest[n]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
raw=subprocess.check_output(['scontrol','show','job','-o','12577'],env=env,timeout=20);assert not shape.search(raw)
fields=dict(x.split('=',1) for x in raw.decode().split() if '=' in x)
status={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':commit,
 'queue':{k:fields.get(k) for k in ('JobId','JobState','Reason','RunTime','StartTime','TimeLimit','ReqNodeList','TresPerNode','Restarts')},
 'source_files_verified':len(ready['hashes']),'model_effect_measured':False,'source_admission':False,
 'exporter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
for n,value in [('STATUS.json',status),('MANIFEST.json',manifest)]:
 with (out/n).open('x') as f:json.dump(value,f,sort_keys=True,indent=2)
archive=Path('/tmp/pivot-12577-queued-receipts.tar');assert not archive.exists()
with tarfile.open(archive,'w') as t:
 for p in sorted(out.iterdir()):t.add(p,arcname=p.name,recursive=False)
print(json.dumps({'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'status':status,'files':len(names)+2}))
