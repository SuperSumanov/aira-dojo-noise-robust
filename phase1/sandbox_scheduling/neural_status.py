"""Metadata-only monitor for the fixed R14 neural batch, no raw logs/scores."""
import json
import time
from lifecycle_pilot import read,sha

def main(kind='neural'):
 if kind=='neural':
  from neural_pool_trial import R,schedule
 elif kind=='pipeline':
  from pipeline_trial import R,schedule
 elif kind=='homogeneous':
  from homogeneous_trial import R,schedule
 else:raise ValueError('monitor scope')
 rows=[]
 for row in [dict(index=36,arm='warmup')]+schedule():
  ep=R/f'episode-{row["index"]}';item=dict(**row)
  for name in ('started','candidate_started','candidate_ended','closed'):
   item[name]=(ep/f'{name}.json').exists()
  if item['started']:
   item['elapsed_since_worker_start']=time.time()-read(ep/'started.json')['start']
  if (ep/'completed.json').exists():
   done=read(ep/'completed.json')
   item.update({k:done.get(k) for k in ('complete','error_type','exec_seconds','timed_out')})
   training=done.get('gpu_training')
   item['gpu_steps']=training.get('steps') if isinstance(training,dict) else None
   item['gpu_training_verified']=bool(training)
  rows.append(item)
 result=dict(job=read(R/'launch.json')['job'],plan_sha256=sha(R/'plan.json'),rows=rows,
             blocks_complete=sum((R/f'block-{i}.json').exists() for i in range({'neural':6,'pipeline':9,'homogeneous':12}[kind])))
 if (R/'closed.json').exists():result['batch_closed']=read(R/'closed.json')
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['neural','pipeline','homogeneous'],default='neural')
 main(parser.parse_args().kind)
