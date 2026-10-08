"""Metadata-only monitor for the fixed R14 neural batch, no raw logs/scores."""
import json
import time
from lifecycle_pilot import read,sha
from neural_pool_trial import R,schedule

def main():
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
   item['gpu_steps']=done.get('gpu_training',{}).get('steps')
  rows.append(item)
 result=dict(job=read(R/'launch.json')['job'],plan_sha256=sha(R/'plan.json'),rows=rows,
             blocks_complete=sum((R/f'block-{i}.json').exists() for i in range(6)))
 if (R/'closed.json').exists():result['batch_closed']=read(R/'closed.json')
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()
