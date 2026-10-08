"""Independent structural/timing audit of a CLOSED fixed four-program trial.

No candidate re-execution and no raw prediction or quality-label access.
"""
import ast
from collections import Counter,defaultdict
import json
from pathlib import Path
import statistics
from lifecycle_pilot import read,sha,SECRET,write

R=Path('/research/d7/spc/yzyang4/scheduling-pool-20261008-v2')

def main():
 plan=read(R/'plan.json');summary=read(R/'readout-v1/summary.json');runs=summary['runs']
 expected={(program,arm):3 for program in (0,1,4,3) for arm in ('serial','share2','one_gpu')}
 if Counter((r['program'],r['arm']) for r in runs)!=Counter(expected):raise ValueError('matrix denominator')
 if sorted(r['index'] for r in runs)!=list(range(36)):raise ValueError('slot identities')
 blocks=[];durations=defaultdict(dict);programs=[]
 for b in range(9):
  record=read(R/f'block-{b}.json');samples=read(R/f'telemetry-{b}.json')
  own=[r for r in runs if r['index']//4==b]
  if len(own)!=4 or any(r['arm']!=record['arm'] or r['repeat']!=record['repeat'] for r in own):raise ValueError('block correspondence')
  complete=all(r['status']=='complete' for r in own)
  raw=[read(R/f'episode-{r["index"]}/completed.json') for r in own]
  if complete and not all(d['complete'] for d in raw):raise ValueError('summary status mismatch')
  spans=[];missing_intervals=[]
  for r in own:
   ep=R/f'episode-{r["index"]}'
   if (ep/'candidate_started.json').exists() and (ep/'candidate_ended.json').exists():
    spans.append((read(ep/'candidate_started.json')['time'],read(ep/'candidate_ended.json')['time']))
   else:missing_intervals.append(r['index'])
  points=sorted({t for a,z in spans for t in (a,z)})
  union=shared=0.
  for left,right in zip(points,points[1:]):
   n=sum(a<right and z>left for a,z in spans)
   if n:union+=right-left
   if n>1:shared+=right-left
  span=record['end']-record['start']
  if union>span+.01:raise ValueError('candidate interval outside block')
  durations[record['repeat']][record['arm']]=span if complete else None
  blocks.append(dict(block=b,arm=record['arm'],repeat=record['repeat'],complete=complete,makespan_seconds=span,
   candidate_time_union_seconds=union,candidate_overlap_seconds=shared,missing_candidate_intervals=missing_intervals,
   outside_candidate_intervals_seconds=span-union if not missing_intervals else None,
   samples=len(samples),gpu_peak_memory_mib=max((s['memory_mib'] for s in samples),default=None),
   max_resident_gpu_clients=max((len(s['apps']) for s in samples),default=None),
   gpu_clients_not_proof_of_simultaneous_kernels=True))
 ratios={}
 for left,right in [('serial','share2'),('serial','one_gpu'),('share2','one_gpu')]:
  name=left+'_over_'+right
  values=[durations[k][left]/durations[k][right] for k in sorted(durations) if durations[k][left] and durations[k][right]]
  reported=summary['ratios'][name]['pairs']
  if values!=[r['ratio'] for r in reported]:raise ValueError('independent timing disagreement')
  ratios[name]=dict(values=values,median=statistics.median(values) if values else None)
 for program in (0,1,4,3):
  p=R/f'programs/{program}.py';raw=p.read_bytes()
  if sha(p)!=plan['programs'][program]['source_sha256'] or SECRET.search(raw):raise ValueError('source drift/credential')
  tree=ast.parse(raw.decode());seed_settings=[]
  for node in ast.walk(tree):
   if isinstance(node,ast.Assign):
    for target in node.targets:
     if isinstance(target,ast.Name) and 'seed' in target.id.lower() and isinstance(node.value,ast.Constant):seed_settings.append(dict(line=node.lineno,name=target.id,value=node.value.value))
   if isinstance(node,ast.Call):
    for k in node.keywords:
     if k.arg in ('seed','random_seed','random_state') and isinstance(k.value,ast.Constant):seed_settings.append(dict(line=node.lineno,name=k.arg,value=k.value.value))
  fits=[dict(index=r['index'],arm=r['arm'],repeat=r['repeat'],fit_receipts=r.get('completion',{}).get('gpu_training'),output_sha256=r.get('output_sha256')) for r in runs if r['program']==program]
  programs.append(dict(program=program,source_sha256=sha(p),harness_seed=130701,source_seed_literal_occurrences=seed_settings,
   source_seed_occurrences_not_dynamic_coverage=True,runs=fits))
 result=dict(job=summary['job'],summary_sha256=sha(R/'readout-v1/summary.json'),plan_sha256=sha(R/'plan.json'),
  denominator_verified=36,blocks=blocks,ratios=ratios,programs=programs,no_candidate_execution=True,no_score_or_prediction_values_read=True,
  boundary='Whole fixed pool and same-source restarts only; interval decomposition is descriptive, not a counterfactual speedup attribution.')
 out=R/'audit-v1';out.mkdir(mode=0o700,exist_ok=False);write(out/'summary.json',result)
 print(json.dumps(dict(job=result['job'],audit_sha256=sha(out/'summary.json'),ratios=ratios),sort_keys=True))

if __name__=='__main__':main()
