"""Frozen full-denominator neural scheduling readout; no quality labels."""
import itertools
import json
import os
import subprocess
from lifecycle_pilot import read,write,sha
from throughput_readout import load_predictions,difference,distribution,overlap
from neural_pool_trial import R,schedule

def main():
 plan=read(R/'plan.json');job=read(R/'launch.json')['job']
 env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
 raw=subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20)
 matches=[s.split('|') for s in raw.splitlines() if s.split('|')[0]==job]
 if len(matches)!=1 or matches[0][1] in ('PENDING','RUNNING','COMPLETING'):raise ValueError('not terminal')
 alloc=matches[0];tres=dict(v.split('=',1) for v in alloc[3].split(',') if '=' in v)
 if int(tres['gres/gpu'])!=1 or int(tres['cpu'])!=6:raise ValueError('resource contract')
 runs=read(R/'runs.json')
 if [r['index'] for r in runs]!=list(range(12)):raise ValueError('denominator')
 outputs={};steps={};blocks=[]
 for r in runs:
  if r['status']!='complete':continue
  ep=R/f'episode-{r["index"]}';done=read(ep/'completed.json');path=ep/'work/submission.csv'
  if sha(path)!=done['output']['sha256'] or not done['complete']:raise ValueError('output drift')
  header,rows=load_predictions(path)
  if any(len(v)!=len(header)-1 for v in rows.values()):raise ValueError('output width')
  outputs[r['index']]=(header,rows);steps[r['index']]=done['gpu_training']['steps']
 for b in range(6):
  if not (R/f'block-{b}.json').exists():continue
  record=read(R/f'block-{b}.json');samples=read(R/f'telemetry-{b}.json');own=runs[2*b:2*b+2];intervals=[]
  for r in own:
   ep=R/f'episode-{r["index"]}'
   if (ep/'candidate_started.json').exists() and (ep/'candidate_ended.json').exists():
    intervals.append((read(ep/'candidate_started.json')['time'],read(ep/'candidate_ended.json')['time']))
  blocks.append(dict(block=b,arm=record['arm'],repeat=record['repeat'],makespan=record['end']-record['start'],
   completed=sum(r['status']=='complete' for r in own),candidate_overlap=overlap(intervals),
   max_resident_gpu_clients=max((len(s['apps']) for s in samples),default=None),
   gpu_peak_memory_mib=max((s['memory_mib'] for s in samples),default=None),telemetry_samples=len(samples),
   multi_client_samples=sum(len(s['apps'])>1 for s in samples),not_kernel_concurrency_measurement=True))
 ratios=[]
 for rep in range(3):
  own={b['arm']:b for b in blocks if b['repeat']==rep}
  if set(own)=={'serial','share2'} and all(v['completed']==2 for v in own.values()):
   ratios.append(dict(repeat=rep,ratio=own['serial']['makespan']/own['share2']['makespan']))
 equivalence=[]
 for program in (0,1):
  rows=[r for r in runs if r['program']==program and r['index'] in outputs];pairs=[]
  for x,y in itertools.combinations(rows,2):
   pairs.append(dict(indices=[x['index'],y['index']],arms=[x['arm'],y['arm']],**difference(outputs[x['index']],outputs[y['index']])))
  within=max((v['max_abs'] for v in pairs if v['arms'][0]==v['arms'][1]),default=None)
  cross=max((v['max_abs'] for v in pairs if v['arms'][0]!=v['arms'][1]),default=None)
  step_counts=[steps[r['index']] for r in rows]
  equivalence.append(dict(program=program,available_outputs=len(rows),steps=step_counts,pairs=pairs,
   all_six_present=len(rows)==6,step_counts_equal=len(set(step_counts))==1 if len(rows)==6 else None,
   max_within_arm=within,max_cross_arm=cross,numerical_gate=(cross<=within+1e-6 and cross<=1e-5) if len(rows)==6 else None,
   tolerance_is_not_quality_guarantee=True))
 speed=distribution([v['ratio'] for v in ratios]);complete=sum(r['status']=='complete' for r in runs)
 result=dict(job=job,source_commit=plan['source_commit'],plan_sha256=sha(R/'plan.json'),planned=12,
  attempted=sum(r['status']!='not_started' for r in runs),completed=complete,
  allocation_state=alloc[1],allocation_exit=alloc[4],allocation_seconds=int(alloc[2]),whole_pool_gpu_hours=int(alloc[2])/3600,
  within_cap=int(alloc[2])<=5400,blocks=blocks,paired_ratios=ratios,speedup=speed,output_equivalence=equivalence,runs=runs,
  exploratory_gate=complete==12 and len(ratios)==3 and speed['median']>=1.05 and all(v['step_counts_equal'] and v['numerical_gate'] for v in equivalence),
  boundary='Two fixed public-training-derived inputs, unchanged programs and source-seed restarts. No quality scores, live search, novel method or population inference.')
 out=R/'readout-v1';out.mkdir(mode=0o700,exist_ok=False);write(out/'summary.json',result)
 print(json.dumps({k:result[k] for k in ('job','planned','attempted','completed','allocation_seconds','whole_pool_gpu_hours','speedup','exploratory_gate')},sort_keys=True))

if __name__=='__main__':main()
