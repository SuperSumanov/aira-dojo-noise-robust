"""Bounded deployment/copy/independent byte verification; no tar payload parsing."""
import datetime as dt,hashlib,json,os,re,subprocess,sys,tarfile,time
from pathlib import Path
B=Path('/research/d7/spc/yzyang4')
SOURCE=B/'senior-0906-source-20260908'
COPY=B/'senior-0906-sync-20260908'
ROOT=B/'external/senior_data/mle'
META=B/'senior-0906-metadata-20260908/private_inventory.json'
PACKAGE=Path('/tmp/senior-0906-source-20260908.tar')
PACKAGE_SHA='3cf86fcc11d89749f543e7c10850d3d42a76c8897ff549a4a5ed41a524cc2305'
COMMIT='cef7ac01b1fa5745a733bc2b3dad3af42bb1c6d6'
PY=B/'venvs/exp/bin/python'
FILES={'phase1/scripts/sync_senior_0906_bounded_20260908.py','phase1/tests/test_sync_senior_0906.py','phase1/SENIOR_0906_COPY_PREFLIGHT_20260908.md'}
LATEST='6db37288ac0fe2ca1b833ff63c3b10318cd13610c023a9d2412c194a67dfd116'
SECRET=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()

def save(p,obj):
    raw=(json.dumps(obj,sort_keys=True,indent=2)+'\n').encode();assert not SECRET.search(raw)
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    p.chmod(0o400)

def fp(p):
    assert p.resolve()==p and p.is_file() and not p.is_symlink()
    s=p.stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode,s.st_uid,s.st_nlink]

def olds():
    return {str(p.relative_to(ROOT)):fp(p) for p in ROOT.glob('*/*.tar.gz') if p.parent.name!='0906'}

def checked():
    r=json.loads((SOURCE/'READY.json').read_bytes());assert r['commit']==COMMIT
    assert sha(PACKAGE)==r['package_sha256']==PACKAGE_SHA
    assert all(sha(SOURCE/n)==h for n,h in r['source_files'].items())
    assert (B/'prospective_decision_v1/LATEST').read_text().strip()==LATEST
    assert olds()==json.loads((SOURCE/'old_archive_metadata.private.json').read_bytes())
    return r

def prepare():
    assert not SOURCE.exists() and sha(PACKAGE)==PACKAGE_SHA and PACKAGE.stat().st_size<1048576
    SOURCE.mkdir(mode=0o700);hashes={}
    with tarfile.open(PACKAGE,'r:') as t:
        members=t.getmembers();fs=[m for m in members if m.isfile()]
        assert {m.name for m in fs}==FILES and len(fs)==len(FILES)
        assert all(m.isdir() or m.isfile() for m in members)
        for m in fs:
            p=SOURCE/m.name;assert p.is_relative_to(SOURCE) and m.size<100000
            raw=t.extractfile(m).read();assert not SECRET.search(raw)
            p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:f.write(raw)
            p.chmod(0o400);hashes[m.name]=sha(p)
    env=dict(os.environ,PYTHONPATH=str(SOURCE),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='')
    r=subprocess.run([str(PY),'-B','-m','pytest','-q','-p','no:cacheprovider','phase1/tests/test_sync_senior_0906.py'],cwd=SOURCE,env=env,capture_output=True,timeout=90)
    assert not SECRET.search(r.stdout+r.stderr)
    with (SOURCE/'tests.log').open('xb') as f:f.write(r.stdout+r.stderr)
    assert r.returncode==0 and b'20 passed' in r.stdout
    prior=olds();assert len(prior)==343
    save(SOURCE/'old_archive_metadata.private.json',prior)
    ready=dict(commit=COMMIT,package_sha256=PACKAGE_SHA,source_files=hashes,linux_tests=20,test_log_sha256=sha(SOURCE/'tests.log'),original_archives=343)
    save(SOURCE/'READY.json',ready)
    checked();print(json.dumps(dict(status='SOURCE_READY_NOT_DOWNLOADED',commit=COMMIT,linux_tests=20,ready_sha256=sha(SOURCE/'READY.json'))))

def run_copy():
    checked();assert not COPY.exists()
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='')
    with (SOURCE/'copy.private.log').open('xb') as f:
        r=subprocess.run([str(PY),'-B',str(SOURCE/'phase1/scripts/sync_senior_0906_bounded_20260908.py')],cwd=SOURCE,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1830)
    save(SOURCE/'COPY_EXIT.json',dict(returncode=r.returncode,log_sha256=sha(SOURCE/'copy.private.log'),commit=COMMIT))
    assert r.returncode==0
    checked();raw=(COPY/'safe_receipt.json').read_bytes();assert not SECRET.search(raw)
    print(raw.decode())

def verify():
    checked();assert not (COPY/'FAILED.json').exists()
    raw=(COPY/'safe_receipt.json').read_bytes();assert not SECRET.search(raw)
    r=json.loads(raw);m=json.loads((COPY/'private_manifest.json').read_bytes());meta=json.loads(META.read_bytes())
    assert sha(COPY/'private_manifest.json')==r['private_manifest_sha256']
    assert sha(META)==m['source_manifest_sha256']=='bd50b189f01f8730887ecfff4487d23c49228a039f3ccacff8abd3f15800042c'
    rows=m['records'];assert len(rows)==11 and len({x['sha256'] for x in rows})==11
    assert {(x['drive_id'],x['name']) for x in rows}=={(x[0],x[1]) for x in meta['archives']}
    target=ROOT/'0906';assert target.resolve()==target and not target.is_symlink()
    assert {p.name for p in target.iterdir()}=={x['name'] for x in rows}
    for x in rows:
        p=target/x['name'];before=fp(p)
        assert p.parent==target and before[2]==x['bytes'] and before[3]==x['mtime_ns']
        assert before[5]&0o777==0o400 and before[6]==os.getuid() and before[7]==1
        got=subprocess.check_output(['sha256sum','--',str(p)],timeout=30).decode().split()[0]
        assert got==x['sha256']==sha(p) and fp(p)==before
    n=sum(x['bytes'] for x in rows);assert n==r['bytes'] and len(list(ROOT.glob('*/*.tar.gz')))==354
    assert r['archive_contents_parsed'] is False and r['protected_outcome_values_read'] is False
    age=max(x['mtime_ns']/1e9 for x in rows)+21600
    v=dict(status='INDEPENDENT_OPAQUE_COPY_VERIFIED_NOT_INTAKE_OR_TRAINING',observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        commit=COMMIT,archives=len(rows),compressed_bytes=n,source_archives=354,safe_receipt_sha256=hashlib.sha256(raw).hexdigest(),
        private_manifest_sha256=r['private_manifest_sha256'],gnu_and_python_hash_agree=True,old_archive_metadata_unchanged=True,
        old_archive_payloads_rehashed=False,latest_unchanged=LATEST,protected_outcome_values_read=False,archive_contents_parsed=False,
        all_files_six_hour_age_at_utc=dt.datetime.fromtimestamp(age,dt.timezone.utc).isoformat(),intake_age_satisfied=time.time()>=age,
        training_source_qualified=False,gpu_jobs=0,paid_api_calls=0)
    save(SOURCE/'INDEPENDENT_COPY.json',v);print(json.dumps(v,sort_keys=True))

os.umask(0o077)
try:
    assert sys.argv[1:] in (['prepare'],['run'],['verify'])
    {'prepare':prepare,'run':run_copy,'verify':verify}[sys.argv[1]]()
except Exception as e:
    print(json.dumps(dict(status='OPERATION_FAILED_CLOSED',error_type=type(e).__name__,automatic_retry=False)));raise SystemExit(1)
