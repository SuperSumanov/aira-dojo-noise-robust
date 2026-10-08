"""Read-only public-training input coverage, not evaluation labels or quality."""
import collections
import hashlib
import json
from pathlib import Path
import signal
import time
from lifecycle_pilot import read

R=Path('/research/d7/spc/yzyang4/scheduling-throughput-20261007-v1')


def main():
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('180s public input scan cap')))
 signal.alarm(180); started=time.monotonic()
 plan=read(R/'plan.json')
 src=[p for p in plan['public_inputs'] if p['path'].endswith('/tabular-playground-series-dec-2021/prepared/public/train.csv')]
 if len(src)!=1:raise ValueError('public training source identity')
 path=Path(src[0]['path']); before=path.stat(); digest=hashlib.sha256(); counts=collections.Counter(); first={}
 with path.open('rb') as f:
  header=next(f);digest.update(header)
  if header.rstrip().split(b',')[-1]!=b'Cover_Type':raise ValueError('public training schema')
  for index,line in enumerate(f):
   digest.update(line)
   # This fixed source is a numeric CSV. Refuse a quoted/multiline variant.
   if b'"' in line:raise ValueError('numeric CSV assumption changed')
   label=int(line.rstrip().rsplit(b',',1)[-1]);counts[label]+=1;first.setdefault(label,index)
 after=path.stat()
 if digest.hexdigest()!=src[0]['sha256'] or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('source drift')
 import csv
 with (R/'data-dec/train.csv').open(newline='') as f:
  small=collections.Counter(int(r['Cover_Type']) for r in csv.DictReader(f))
 print(json.dumps(dict(status='public_training_only',source_sha256=digest.hexdigest(),
  full_rows=sum(counts.values()),full_class_counts=dict(counts),first_public_row_per_class=first,
  fixture_rows=sum(small.values()),fixture_class_counts=dict(small),missing_fixture_classes=sorted(set(counts)-set(small)),
  elapsed_seconds=time.monotonic()-started,private_labels_accessed=False,candidate_executions=0),sort_keys=True))


if __name__=='__main__':main()
