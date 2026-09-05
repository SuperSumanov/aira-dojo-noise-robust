"""Recoverable copy-verify-unlink of exactly reviewed disposable wheel bodies."""
import hashlib,json,os,stat,subprocess,tempfile,datetime
from pathlib import Path
base=Path('/research/d7/spc/yzyang4/cache/pip/http-v2')
inv=Path('/tmp/public-pip-body-inventory-20260905.json')
raw=inv.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='0aa1b80cd50f22bae484ba9e3f874333021e56576ec4d20c2a05654e56c91cdf'
rows=json.loads(raw);assert len(rows)==11
assert base.resolve(strict=True)==base
def safe(row):
    p=Path(row['path']);s=p.lstat()
    assert base in p.parents and p.resolve(strict=True)==p and p.suffix=='.body'
    assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.getuid()
    assert (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)==(row['device'],row['inode'],row['bytes'],row['mtime_ns'])
    return p
targets={str(safe(r)) for r in rows}
def live_gate():
    denied=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdecimal():continue
        try:
            if proc.stat().st_uid!=os.getuid():continue
            comm=(proc/'comm').read_text().strip()
            if comm in {'sshd','systemd','(sd-pam)'}:continue
            for entry in (proc/'fd').iterdir():
                try:assert os.readlink(entry) not in targets,'Live cache file reference'
                except FileNotFoundError:pass
        except (FileNotFoundError,ProcessLookupError):pass
        except PermissionError:denied.append(proc.name)
    assert not denied,'Uninspectable same-user process'
live_gate()
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
q=subprocess.check_output(['squeue','-h','-u','yzyang4','-o','%i,%T,%R'],env=env,text=True,timeout=20).strip()
assert q=='12510,PENDING,(JobHeldUser)',q
root=Path(tempfile.mkdtemp(prefix='research-pip-cache-backup-',dir='/tmp'))
assert root.parent==Path('/tmp') and root.resolve()==root
assert os.statvfs(root).f_bavail*os.statvfs(root).f_frsize>sum(r['bytes'] for r in rows)*2
(root/'inventory.json').write_bytes(raw)
(root/'intent.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'strategy':'copy fsync sha256 verify before unlink; remote tmp backup retained','files':len(rows),'research_target':str(base)}))
backups=[]
for row in rows:
    src=safe(row);dst=root/src.name
    h=hashlib.sha256()
    with src.open('rb') as f,dst.open('xb') as out:
        while block:=f.read(4*1024**2):h.update(block);out.write(block)
        out.flush();os.fsync(out.fileno())
    os.chmod(dst,0o600)
    hh=hashlib.sha256()
    with dst.open('rb') as f:
        while block:=f.read(4*1024**2):hh.update(block)
    assert h.hexdigest()==hh.hexdigest() and dst.stat().st_size==row['bytes']
    safe(row);backups.append({**row,'backup':str(dst),'sha256':h.hexdigest()})
(root/'verified_backups.json').write_text(json.dumps(backups,sort_keys=True,indent=2))
live_gate()
for row in rows:safe(row)
with (root/'removal_journal.jsonl').open('x') as journal:
    for row in rows:
        p=safe(row);p.unlink()
        journal.write(json.dumps({'removed':str(p),'backup_verified':True})+'\n');journal.flush();os.fsync(journal.fileno())
result={'status':'REVIEWED_PUBLIC_PIP_BODIES_RELOCATED','backup_root':str(root),'files':len(rows),'removed_allocated_bytes':sum(r['allocated_bytes'] for r in rows),'bytes':sum(r['bytes'] for r in rows),'all_backups_sha256_verified':True,'trained_checkpoints_or_corpus_touched':False,'installed_environments_modified':False,'recovery':'Copy from remote temporary backup or redownload exact public package/version; tmp is not permanent storage.'}
(root/'result.json').write_text(json.dumps(result,sort_keys=True,indent=2))
print(json.dumps(result,sort_keys=True))
