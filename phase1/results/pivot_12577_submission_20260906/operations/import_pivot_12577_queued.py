import hashlib,json,re,tarfile
from pathlib import Path
archive=Path('tmp/pivot-12577-queued-receipts.tar')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='6688c5f3f8d996440cd2058a0a162a7cd582e4b7041b3cbf807ca8337cfffc24'
output=Path('phase1/results/pivot_12577_submission_20260906')
assert not output.exists()
shape=re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
with tarfile.open(archive) as t:
 members=t.getmembers();assert len(members)==19 and len({m.name for m in members})==19
 assert all(m.isfile() and len(Path(m.name).parts)==1 and not Path(m.name).is_absolute() for m in members)
 records={m.name:t.extractfile(m).read() for m in members}
 assert all(not shape.search(raw) for raw in records.values())
 manifest=json.loads(records['MANIFEST.json']);assert set(manifest)==set(records)-{'MANIFEST.json','STATUS.json'}
 for n,record in manifest.items():assert record=={'bytes':len(records[n]),'sha256':hashlib.sha256(records[n]).hexdigest()}
 assert json.loads(records['RELEASED.json'])=={'job_id':'12577','commit':'50f2967ad2637850742075454440aea2c5fa8a28'}
 assert json.loads(records['space-probe.json'])['allocated_bytes']==68719476736
 assert b'171 passed' in records['cpu-tests.log']
 output.mkdir()
 for name,raw in records.items():
  with (output/name).open('xb') as f:f.write(raw)
print(json.dumps({'verified_files':len(records),'source_files':len(json.loads(records['READY.json'])['hashes']),
 'cpu_tests':171,'job_id':'12577','classification':'RELEASED_AND_QUEUED_NOT_GPU_OR_EFFECT_ACCEPTANCE'}))
