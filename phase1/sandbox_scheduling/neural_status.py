"""Metadata-only monitor for the fixed R14 neural batch, no raw logs/scores."""
import json
import time
from lifecycle_pilot import read,sha

def validated_completion(done, closed):
 return (done.get('complete') is True and done.get('error_type') is None
         and bool(done.get('output')) and closed.get('returncode') == 0)

def main(kind='neural'):
 if kind=='neural':
  from neural_pool_trial import R,schedule
 elif kind=='pipeline':
  from pipeline_trial import R,schedule
 elif kind=='homogeneous':
  from homogeneous_trial import R,schedule
 elif kind=='replication':
  from neural_node_replication import R
  from neural_pool_trial import schedule
 elif kind=='full-input':
  from neural_full_input_trial import R
  from neural_pool_trial import schedule
 elif kind=='overlap':
  from neural_overlap_control import R,schedule
 elif kind=='confirmation':
  from neural_full_confirmation import R
  from neural_pool_trial import schedule
 elif kind=='overlap-retry':
  from neural_overlap_retry import R
  from neural_overlap_control import schedule
 elif kind=='width':
  from neural_width_trial import R,schedule
 elif kind=='extension':
  from neural_extension_20261010 import R
  from neural_overlap_control import schedule
 elif kind=='reverse-independent':
  from neural_reverse_independent_20261010 import old
  R,schedule=old.e.R,old.reverse_schedule
 elif kind=='reverse-entry-repair':
  from neural_reverse_entry_repair_20261010 import old
  R,schedule=old.e.R,old.reverse_schedule
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
   closed=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
   item['reported_complete']=done.get('complete')
   item['returncode']=closed.get('returncode')
   item['complete']=validated_completion(done,closed)
   training=done.get('gpu_training')
   item['gpu_steps']=training.get('steps') if isinstance(training,dict) else None
   item['gpu_training_verified']=bool(training)
   if done.get('complete') is False:
    item['cell_statuses']=[{k:read(path).get(k) for k in ('stage','exit_code','timed_out','exec_seconds','timeout_phase')} for path in sorted(ep.glob('cell-*.json'))]
    path=ep/'cell-0.private.txt'
    if path.exists():
     private_text=path.read_text(errors='replace').lower()
     item['prelude_diagnostic_terms']=[term for term in ('kernel readiness','kernel did not','kernel didn\'t','timeout','cuda out of memory','address already in use','connection refused','no route to host') if term in private_text]
  rows.append(item)
 result=dict(job=read(R/'launch.json')['job'],plan_sha256=sha(R/'plan.json'),rows=rows,
             blocks_complete=sum((R/f'block-{i}.json').exists() for i in range({'neural':6,'pipeline':9,'homogeneous':12,'replication':6,'full-input':6,'overlap':6,'confirmation':6,'overlap-retry':6,'width':9,'extension':6,'reverse-independent':6,'reverse-entry-repair':6}[kind])))
 if (R/'closed.json').exists():result['batch_closed']=read(R/'closed.json')
 print(json.dumps(result,sort_keys=True))

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=['neural','pipeline','homogeneous','replication','full-input','overlap','confirmation','overlap-retry','width','extension','reverse-independent','reverse-entry-repair'],default='neural')
 main(parser.parse_args().kind)
