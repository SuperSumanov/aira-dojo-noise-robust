import datetime,json,os,subprocess,tempfile,hashlib
from pathlib import Path
root=Path('/research/d7/spc/yzyang4/critic-zero3-engineering')
assert root.resolve(strict=True)==root and root.stat().st_uid==os.getuid()
out=Path(tempfile.mkdtemp(prefix='zero3-storage-recovery-',dir='/tmp'))
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'root':str(root),'reserve_bytes':1024**3}
test=Path(tempfile.mkdtemp(prefix='own-space-check-',dir=root));assert test.parent==root and test.resolve()==test
fd,path=tempfile.mkstemp(prefix='reservation-',dir=test);p=Path(path)
try:
    assert os.write(fd,b'\0'*65536)==65536;os.fsync(fd)
    os.posix_fallocate(fd,0,receipt['reserve_bytes']);os.fsync(fd)
    s=os.fstat(fd);assert s.st_blocks*512>=receipt['reserve_bytes']
    receipt.update(status='PASS',allocated_bytes=s.st_blocks*512,file_bytes=s.st_size)
except OSError as exc:
    receipt.update(status='FAIL',errno=exc.errno)
finally:
    s=os.fstat(fd);os.close(fd)
    assert p.resolve(strict=True).parent==test and p.stat().st_ino==s.st_ino
    p.unlink();test.rmdir()
(out/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2))
print(json.dumps({'receipt_root':str(out),**receipt},sort_keys=True))
assert receipt['status']=='PASS'
# Cancel only the read-only du started in this turn; its full-root scan is unnecessary.
proc=Path('/proc/1522946')
if proc.exists():
    if proc.stat().st_uid==os.getuid() and (proc/'cmdline').read_bytes()==b'du\0-x\0-h\0--max-depth=1\0/research/d7/spc/yzyang4\0':
        os.kill(1522946,15)
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
raw=subprocess.check_output(['scontrol','show','job','-o','12510'],env=env,text=True,timeout=20)
d=dict(x.split('=',1) for x in raw.split() if '=' in x)
assert d['JobState']=='PENDING' and d['Reason']=='JobHeldUser' and d['UserId'].startswith('yzyang4(')
assert d['Command']=='/research/d7/spc/yzyang4/worktrees/zero3-engineering-d22a17f3f6e6/phase1/scripts/zero3_session_engineering_20260905.sbatch'
assert d['TimeLimit']=='00:30:00' and d['TresPerNode']=='gpu:pro6000:2' and d['ReqNodeList']=='projgpu39'
assert d['Requeue']==d['Restarts']=='0'
(out/'held.txt').write_text(raw)
(out/'release_intent.json').write_text(json.dumps({'job':12510,'storage_receipt_sha256':hashlib.sha256((out/'receipt.json').read_bytes()).hexdigest(),'matrix_changed':False}))
subprocess.run(['scontrol','release','12510'],env=env,check=True,timeout=20)
raw=subprocess.check_output(['scontrol','show','job','-o','12510'],env=env,text=True,timeout=20)
(out/'released.txt').write_text(raw)
d=dict(x.split('=',1) for x in raw.split() if '=' in x)
assert d['JobState'] in ('PENDING','RUNNING') and d['Reason']!='JobHeldUser'
print(json.dumps({'job':12510,'state':d['JobState'],'reason':d['Reason'],'storage_test':'1GiB actual allocation/fsync PASS','new_jobs_submitted':0,'receipt_root':str(out)}))
