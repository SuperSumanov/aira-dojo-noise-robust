"""Export only own synthetic structural artifacts, not checkpoint payloads."""
import hashlib,importlib.metadata,json,os,re,subprocess,tarfile,datetime
from pathlib import Path
root=Path('/tmp/train-input-session-5b6e0bd-H87Jhq');old=Path('/tmp/train-input-session-c0dc128-8admEe')
assert (root/'exit_status.txt').read_text().strip()=='0'
assert json.loads((root/'independent_verification.json').read_text())['trajectories']==20
secret=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
archive=Path('/tmp/train_input_session_5b6e0bd.tar');assert sha(archive)=='5f53119b6dea831cfd5352bd6a3c62d4143cb3bbf4f72c98147a28919455d567'
code=[]
with tarfile.open(archive) as tar:
    for m in tar:
        if m.isfile():
            expected=hashlib.sha256(tar.extractfile(m).read()).hexdigest()
            assert sha(root/'code'/m.name)==expected
            code.append({'path':m.name,'sha256':expected})
meta={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code_commit':'5b6e0bdd65f3e42860fd40e2d28120de90ed6d7e','archive_sha256':sha(archive),'code_files_unchanged':code,'packages':{k:importlib.metadata.version(k) for k in ('torch','accelerate','transformers','deepspeed','safetensors','numpy')},'trace_scope_is_not_os_isolation':True}
(root/'source_binding.json').write_text(json.dumps(meta,sort_keys=True,indent=2))
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
jobs={}
for key,cmd in [('job12510',['scontrol','show','job','-o','12510']),('current_queue',['squeue','-u','yzyang4','-o','%i,%j,%T,%R']),('recent_accounting',['sacct','-u','yzyang4','-S','2026-09-05T18:30:00','-X','-n','-P','-o','JobID,JobName%30,State,Submit,Start,End,AllocTRES%100'])]:
    p=subprocess.run(cmd,env=env,capture_output=True,timeout=25)
    assert p.returncode==0 and not secret.search(p.stdout+p.stderr)
    jobs[key]=p.stdout.decode()
jobs['note']='Original metadata sbatch return/stdout were not persisted due EDQUOT; no matching held/running/accounted metadata job observed; no submission retry.'
probe=['sbatch','--test-only','/research/d7/spc/yzyang4/critic-zero3-engineering/node-metadata/check.sbatch']
p=subprocess.run(probe,env=env,capture_output=True,timeout=25)
assert not secret.search(p.stdout+p.stderr)
jobs['metadata_test_only_recheck']={'argv':probe,'returncode':p.returncode,'stdout':p.stdout.decode(),'stderr':p.stderr.decode(),'creates_job':False}
(root/'scheduler_reconciliation.json').write_text(json.dumps(jobs,sort_keys=True,indent=2))
files={}
def add(p,dest):
    assert dest not in files and p.is_file() and not p.is_symlink()
    raw=p.read_bytes();assert b'\0' not in raw and len(raw)<1024**2 and not secret.search(raw)
    files[dest]=p
for n in ('tests.txt','a.log','b.log','exit_status.txt','independent.log','independent_verification.json','a.trace_audit.json','a.trace_audit_v2.json','b.trace_audit_v2.json','source_binding.json','scheduler_reconciliation.json'):add(root/n,n)
for repeat in ('a','b'):
    for p in sorted((root/repeat).rglob('*')):
        if p.is_file() and p.name in {'summary.json','runs.csv','trajectory.json','manifest.json','observed_0.json','observed_1.json'}:add(p,str(p.relative_to(root)))
for n in ('tests.txt','a.log','exit_status.txt'):add(old/n,'diagnostic_c0dc128/'+n)
for base,dest in [('/tmp/zero3-quota-incident-9i2pimhx','storage/incident'),('/tmp/zero3-storage-recovery-b4xfws7p','storage/recovery')]:
    for p in sorted(Path(base).iterdir()):
        if p.is_file():add(p,dest+'/'+p.name)
backup=Path('/tmp/research-pip-cache-backup-svbm2hko')
for n in ('inventory.json','intent.json','verified_backups.json','removal_journal.jsonl','result.json'):add(backup/n,'storage/cache_relocation/'+n)
metadata=Path('/research/d7/spc/yzyang4/critic-zero3-engineering/node-metadata')
for n in ('SUBMISSION_INTENT.json','check.py','check.sbatch'):add(metadata/n,'metadata_attempt/'+n)
add(Path('/tmp/submit_zero3_cpu_metadata.py'),'operations/submit_zero3_cpu_metadata.py')
for n in ('hold_zero3_quota_20260905.py','relocate_reviewed_pip_bodies.py','inspect_public_pip_bodies.py','verify_zero3_storage_recovery.py','audit_training_input_cpu_trace.py','audit_training_input_cpu_trace_v1.py','run_train_input_session.sh','run_train_input_session_c0dc128.sh','export_training_input_receipts.py'):add(Path('/tmp')/n,'operations/'+n)
inventory={d:{'bytes':p.stat().st_size,'sha256':sha(p)} for d,p in sorted(files.items())}
(root/'artifact_inventory.json').write_text(json.dumps(inventory,sort_keys=True,indent=2))
add(root/'artifact_inventory.json','artifact_inventory.json')
with tarfile.open(root/'safe_artifacts.tar','x') as tar:
    for d,p in sorted(files.items()):tar.add(p,arcname=d,recursive=False)
print(json.dumps({'files':len(files),'archive':str(root/'safe_artifacts.tar'),'sha256':sha(root/'safe_artifacts.tar'),'bytes':(root/'safe_artifacts.tar').stat().st_size,'code_files_unchanged':len(code)},sort_keys=True))
