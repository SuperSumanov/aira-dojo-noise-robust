"""All fixed slots and whole-allocation costs; no quality or raw output export."""
import itertools
import json
import os
import statistics
import subprocess
from pathlib import Path
from lifecycle_pilot import read,write,sha
import fixed_pool_trial as p
from throughput_readout import load_predictions,difference,overlap,distribution


def main():
 plan=read(p.R/'plan.json');job=read(p.R/'launch.json')['job']
 env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
 accounting=subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20)
 matched=[r.split('|') for r in accounting.splitlines() if r.split('|')[0]==job]
 if len(matched)!=1 or matched[0][1] in ('RUNNING','PENDING','COMPLETING'):raise ValueError('allocation not terminal')
 alloc=matched[0];tres=dict(x.split('=',1) for x in alloc[3].split(',') if '=' in x)
 if int(tres['gres/gpu'])!=1 or int(tres['cpu'])!=6:raise ValueError('allocation changed')
 runs=[];outputs={};blocks=[]
 for row in p.schedule():
  ep=p.R/f'episode-{row["index"]}';item=dict(**row,status='not_started')
  if (ep/'started.json').exists():item['status']='incomplete'
  if (ep/'closed.json').exists():item['supervisor']=read(ep/'closed.json');item['status']='failed'
  if (ep/'completed.json').exists():
   done=read(ep/'completed.json');item['completion']={k:v for k,v in done.items() if k!='output'}
   if done.get('complete') and item.get('supervisor',{}).get('returncode')==0:
    item['status']='complete';outputs[row['index']]=load_predictions(ep/'work/submission.csv')
    item['output_sha256']=sha(ep/'work/submission.csv')
  runs.append(item)
 for block in range(9):
  path=p.R/f'block-{block}.json'
  if not path.exists():continue
  record=read(path);rows=[r for r in runs if r['index']//4==block];intervals=[]
  for r in rows:
   ep=p.R/f'episode-{r["index"]}'
   if (ep/'candidate_started.json').exists() and (ep/'candidate_ended.json').exists():
    intervals.append((read(ep/'candidate_started.json')['time'],read(ep/'candidate_ended.json')['time']))
  blocks.append(dict(block=block,arm=record['arm'],repeat=record['repeat'],makespan_seconds=record['end']-record['start'],
   attempted=sum(r['status']!='not_started' for r in rows),completed=sum(r['status']=='complete' for r in rows),
   candidate_overlap=overlap(intervals),telemetry_errors=record['telemetry_errors'],
   candidate_exec_seconds=[r.get('completion',{}).get('exec_seconds') for r in rows]))
 comparisons=[]
 for program in p.PROGRAMS:
  rows=[r for r in runs if r['program']==program and r['index'] in outputs];pairs=[]
  for x,y in itertools.combinations(rows,2):
   pairs.append(dict(indices=[x['index'],y['index']],arms=[x['arm'],y['arm']],**difference(outputs[x['index']],outputs[y['index']])))
  comparisons.append(dict(program=program,available_outputs=len(rows),all_nine_present=len(rows)==9,
   all_outputs_exactly_equal=all(v['max_abs']==0 for v in pairs) if len(rows)==9 else None,pairs=pairs))
 ratios={}
 for left,right in [('serial','share2'),('serial','one_gpu'),('share2','one_gpu')]:
  values=[]
  for repeat in range(3):
   selected={b['arm']:b for b in blocks if b['repeat']==repeat}
   if left in selected and right in selected and selected[left]['completed']==selected[right]['completed']==4:
    values.append(dict(repeat=repeat,ratio=selected[left]['makespan_seconds']/selected[right]['makespan_seconds']))
  ratios[left+'_over_'+right]=dict(pairs=values,summary=distribution([r['ratio'] for r in values]),complete_three_pairs=len(values)==3)
 result=dict(job=job,allocation_state=alloc[1],allocation_exit=alloc[4],allocation_seconds=int(alloc[2]),
  whole_pool_gpu_hours=int(alloc[2])/3600,within_cap=int(alloc[2])<=5400,planned=36,
  attempted=sum(r['status']!='not_started' for r in runs),completed=sum(r['status']=='complete' for r in runs),
  source_commit=plan['source_commit'],plan_sha256=sha(p.R/'plan.json'),fixture_sha256=sha(p.R/'fixture.json'),
  blocks=blocks,ratios=ratios,output_equivalence=comparisons,runs=runs,
  no_quality_scoring=True,no_semantic_method=True,no_live_search=True,
  boundary='Four small fixed development programs, three tasks, same-seed restarts; new class-covered fixture. Failed slots retained. No generalization or E2E claim.')
 out=p.R/'readout-v1';out.mkdir(mode=0o700,exist_ok=False);write(out/'summary.json',result)
 print(json.dumps({k:result[k] for k in ('job','allocation_state','allocation_seconds','whole_pool_gpu_hours','planned','attempted','completed','ratios')},sort_keys=True))


if __name__=='__main__':main()
