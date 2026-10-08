"""Independent strict shape/hash/numeric equality audit; never export values."""
import csv
import itertools
import json
import math
from pathlib import Path
from lifecycle_pilot import read, sha, write

R=Path('/research/d7/spc/yzyang4/scheduling-pool-20261008-v2')

def strict(path):
 with path.open(newline='') as f:
  reader=csv.reader(f);header=next(reader);rows=list(reader)
 if len(header)<2 or len(set(header))!=len(header) or not rows:raise ValueError('schema')
 if any(len(r)!=len(header) for r in rows):raise ValueError('width')
 values={r[0]:tuple(float(v) for v in r[1:]) for r in rows}
 if len(values)!=len(rows) or any(not math.isfinite(v) for r in values.values() for v in r):raise ValueError('identity/finiteness')
 return header,values

def main():
 report=read(R/'readout-v1/summary.json');result=[]
 for program in (0,1,4,3):
  rows=[r for r in report['runs'] if r['program']==program and r['arm'] in ('serial','share2')]
  if len(rows)!=6 or any(r['status']!='complete' for r in rows):raise ValueError('A/B coverage')
  outputs=[]
  for r in rows:
   ep=R/f'episode-{r["index"]}';p=ep/'work/submission.csv';h=sha(p)
   if h!=r['output_sha256'] or h!=read(ep/'completed.json')['output']['sha256']:raise ValueError('output drift')
   outputs.append(strict(p))
  for a,b in itertools.combinations(outputs,2):
   if a!=b:raise ValueError('numeric or schema difference')
  result.append(dict(program=program,completed_outputs=6,all_pairs_equal=True,verified_pairs=15,
                     rows=len(outputs[0][1]),columns=len(outputs[0][0])))
 out=dict(job=report['job'],readout_sha256=sha(R/'readout-v1/summary.json'),programs=result,
          all_completed_receipt_hashes_match=True,no_quality_labels_read=True,no_values_exported=True)
 dest=R/'output-audit-v1';dest.mkdir(mode=0o700,exist_ok=False);write(dest/'summary.json',out)
 print(json.dumps(dict(**out,audit_sha256=sha(dest/'summary.json')),sort_keys=True))

if __name__=='__main__':main()
