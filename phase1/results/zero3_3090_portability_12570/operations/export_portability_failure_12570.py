import hashlib,json,os,re,subprocess,tarfile
from pathlib import Path
base=Path('/research/d7/spc/yzyang4/critic-zero3-engineering')
root=base/'job-12570';sub=base/'submission-20260906-3090'
out=Path('/tmp/zero3-3090-failure-12570');assert not out.exists();out.mkdir(mode=0o700)
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
raw=subprocess.check_output(['sacct','-X','-n','-P','-j','12570','--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env)
row=raw.decode().strip().split('|')
assert row[:3]==['12570','FAILED','1'] and row[4]=='1:0' and 'gres/gpu=2' in row[3].split(',')
assert (root/'exit_status.txt').read_text().strip()=='1' and not (root/'trajectories').exists()
assert not (root/'driver.log').exists() and 'AssertionError: bin/nvcc' in (root/'worker.log').read_text()
ready=json.loads((sub/'READY.json').read_bytes());control=Path(ready['control'])
assert ready['commit']=='97306120a1c203bb6e72a2b7468a21acbf44371a' and ready['gpu_seconds_upper_bound']==3120
assert all(hashlib.sha256((control/p).read_bytes()).hexdigest()==h for p,h in ready['hashes'].items())
pattern=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
def add(name,raw):
    assert len(raw)<2_000_000 and not pattern.search(raw)
    p=out/name;p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
for n in ('READY.json','RELEASED.json','VERIFIED_HELD.json','SUBMITTED.json','command.json','runtime.json','cpu-tests.log',
          'storage.json','SUBMISSION_INTENT.json','prepare_intent.json','sbatch_status.json','sbatch.stdout','sbatch.stderr'):
    add('submission/'+n,(sub/n).read_bytes())
for n in ('worker.log','exit_status.txt'):add('job/'+n,(root/n).read_bytes())
add('job/sacct.txt',raw)
receipt={'classification':'TOOLCHAIN_PREFLIGHT_FAILURE_NOT_GPU_ACCEPTANCE','job':'12570','node':'gpu28',
    'code_commit':ready['commit'],'source_files_unchanged':len(ready['hashes']),
    'wall_seconds':1,'allocated_gpu_seconds':2,'cap_gpu_seconds':3120,
    'missing_required_tool':'/usr/local/cuda-12.8/bin/nvcc','model_loaded':False,
    'training_driver_started':False,'checkpoints_created':False,'automatic_retry':False,
    'existing_12535_modified':False,'CPU_tests_passed':124,
    'limit':'No general hardware compatibility, production qualification or effect conclusion.'}
add('failure_receipt.json',(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode())
manifest={p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
          for p in out.rglob('*') if p.is_file()}
add('manifest.json',(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode())
archive=Path('/tmp/zero3-3090-failure-12570.tar');assert not archive.exists()
with tarfile.open(archive,'w') as t:
    for p in sorted(out.rglob('*')):
        if p.is_file():t.add(p,arcname=p.relative_to(out).as_posix(),recursive=False)
print(json.dumps({'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(manifest)+1,'receipt':receipt},sort_keys=True))
