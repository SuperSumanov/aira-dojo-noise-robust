import csv
import datetime as dt
import json
from pathlib import Path

root=Path('/research/d7/spc/yzyang4/critic-component-g0/runs/job-12499')
accept=json.loads(Path('/tmp/g0-12499-terminal-checkpoint-20260905.json').read_text())
events=accept['timing']['events']
event_time={r['event']:dt.datetime.fromisoformat(r['utc']) for r in events}
phase_stats={}
for row in csv.DictReader((root/'gpu_telemetry.csv').open()):
    when=dt.datetime.fromisoformat(row['timestamp_utc'].replace('Z','+00:00'))
    phase=('startup' if when<event_time['train_begin'] else
           'training' if when<event_time['optimizer_step_final'] else
           'dev' if when<event_time['dev_evaluate_complete'] else 'save_and_exit')
    key=phase+'_'+row['visible_id'].strip()
    entry=phase_stats.setdefault(key,{'samples':0,'peak_memory_mib':0,'memory_total_mib':int(float(row['memory_total_mib']))})
    entry['samples']+=1
    entry['peak_memory_mib']=max(entry['peak_memory_mib'],int(float(row['memory_used_mib'])))
seconds=accept['timing']['seconds']
train=seconds['train_begin_to_step1']+seconds['step1_to_step10']
saved=(event_time['train_end']-event_time['dev_evaluate_complete']).total_seconds()
out={'job_id':12499,'successful_g0_runs':1,'seed':6,
    'allocation_wall_seconds':accept['jobs']['12499']['elapsed_seconds'],
    'allocation_gpu_hours':accept['jobs']['12499']['elapsed_seconds']*2/3600,
    'launcher_to_train_begin_seconds':seconds['launcher_to_train_begin'],
    'first_optimizer_update_seconds':seconds['train_begin_to_step1'],
    'next_nine_updates_seconds':seconds['step1_to_step10'],
    'next_nine_updates_mean_seconds_not_seed_estimate':seconds['step1_to_step10']/9,
    'training_ten_updates_seconds':train,'dev_551_pairs_seconds':seconds['dev_evaluation'],
    'dev_end_to_train_end_includes_save_seconds':saved,
    'pair_visits':10*128,'phase_telemetry':phase_stats,
    'full_training_gpu_hour_estimate_available':False,
    'limits':['single engineering run; no cross-seed uncertainty estimate',
              'no actual valid-token workload for authoritative future source package',
              'sampled memory peaks can underestimate instantaneous peaks',
              'final-only weights checkpoint, not optimizer/RNG resume acceptance']}
with Path('/tmp/g0-12499-timing-summary-20260905.json').open('x') as f:
    json.dump(out,f,sort_keys=True,indent=2)
print(json.dumps(out,sort_keys=True,indent=2))
