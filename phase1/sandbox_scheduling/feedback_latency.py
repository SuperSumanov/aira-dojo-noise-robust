"""Read-only completed-program return latency, not score/search utility.

Post-hoc descriptive evidence, no selection rule or replacement primary metric.
Block origin and supervisor closure are used, not guessed worker-start origins.
Failures remain in the block denominator; ratios require both full blocks.
"""
import argparse
import json
from pathlib import Path
import statistics
from lifecycle_pilot import read,sha

BASE=Path('/research/d7/spc/yzyang4')
SCOPES={
 'neural':('scheduling-neural-20261008-v1','8da0e849c3203efc2c47c13f134fe9d841ede0f9c3d667789e41ab2aefb95edc'),
 'homogeneous':('scheduling-homogeneous-20261008-v1','1015a7039bdb3436f9d0c0fb2711c045b9c4b48513224bff4c70aa66b381388a'),
 'full-input':('scheduling-neural-full-input-20261008-v2','e836f8c49b13ce52ef02c138b873bc1464cdb147dc06254f656b707ff93afade'),
 'confirmation':('scheduling-neural-full-confirmation-20261008-v1','b8bf8619c61a98db5af35bb2b68f4b9838354c9ccfef166d8dd788ca0b16df7f')}

def block_metrics(start,end,closures):
 if end<start or len(closures)!=2:raise ValueError('block structure')
 successful=[]
 for item in closures:
  if not start<=item['end']<=end:raise ValueError('time order')
  if item['success']:successful.append(item['end']-start)
 full=len(successful)==2
 return dict(complete=full,completed=len(successful),makespan=end-start,
  first_completed_return=min(successful) if successful else None,
  mean_completed_return=statistics.mean(successful) if full else None)

def analyze(kind):
 name,pin=SCOPES[kind];root=BASE/name
 if sha(root/'plan.json')!=pin or not (root/'closed.json').exists():
  raise ValueError('closed fixed scope')
 summary=read(root/'readout-v1/summary.json');runs=summary['runs'];blocks=[]
 for block in summary['blocks']:
  b=block['block'];record=read(root/f'block-{b}.json');closures=[]
  for row in runs[2*b:2*b+2]:
   ep=root/f'episode-{row["index"]}';closed=read(ep/'closed.json')
   done=read(ep/'completed.json') if (ep/'completed.json').exists() else {}
   success=(closed['returncode']==0 and done.get('complete') is True and bool(done.get('output')))
   if success!=(row['status']=='complete'):raise ValueError('completion mismatch')
   closures.append(dict(end=closed['end'],success=success))
  metrics=block_metrics(record['start'],record['end'],closures)
  expected=block['seconds'] if kind=='homogeneous' else block['makespan']
  if abs(metrics['makespan']-expected)>1e-6:raise ValueError('readout time mismatch')
  blocks.append(dict(block=b,arm=block['arm'],repeat=block['repeat'],
   program=record.get('program'),**metrics))
 pairs=[]
 for program in sorted({b['program'] for b in blocks},key=str):
  for repeat in range(3):
   own={b['arm']:b for b in blocks if b['program']==program and b['repeat']==repeat}
   if set(own)!={'serial','share2'} or not all(b['complete'] for b in own.values()):continue
   a,b=own['serial'],own['share2']
   pairs.append(dict(program=program,repeat=repeat,
    serial_over_share2_makespan=a['makespan']/b['makespan'],
    serial_over_share2_first_return=a['first_completed_return']/b['first_completed_return'],
    serial_over_share2_mean_return=a['mean_completed_return']/b['mean_completed_return']))
 return dict(job=summary['job'],plan_sha256=pin,primary_sha256=sha(root/'readout-v1/summary.json'),
  planned=summary['planned'],attempted=summary['attempted'],completed=summary['completed'],
  blocks=blocks,complete_paired_blocks=pairs,
  boundary='Post-hoc descriptive, no quality/utility values. Completed return includes output retrieval and sandbox close. Complete-block ratios are conditional, never remove failed blocks from primary denominator. Existing preparation-interference caveats remain.')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=SCOPES,required=True)
 print(json.dumps(analyze(p.parse_args().kind),sort_keys=True))
