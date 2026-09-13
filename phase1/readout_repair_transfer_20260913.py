"""Frozen T1 reader. Full denominator, paired cases, unknown separate from failure."""
from collections import Counter
import csv
import json
import math
from pathlib import Path
import random
import statistics
from prepare_repair_transfer_20260913 import TASKS, ARMS, read, dump, sha
from run_repair_transfer_20260913 import ROOT, checked, gpu_checked, budget_module, public_budget, now


def comparison(rows, left, right):
    by={(r['case'],r['arm']):r for r in rows}
    cases=sorted({r['case'] for r in rows});d=[];pairs=[]
    for case in cases:
        a,b=by[case,left],by[case,right]
        known=a['repair_success'] is not None and b['repair_success'] is not None
        delta=int(a['repair_success'])-int(b['repair_success']) if known else None
        pairs.append(dict(case=case,task=a['task'],delta=delta))
        if known:d.append(delta)
    interval=None
    if d:
        rng=random.Random(20260913)
        draws=sorted(sum(rng.choices(d,k=len(d)))/len(d) for _ in range(10000))
        interval=[draws[249],draws[9749]]
    return dict(left=left,right=right,planned_pairs=len(cases),known_pairs=len(d),unknown_pairs=len(cases)-len(d),
        wins=sum(x>0 for x in d),ties=sum(x==0 for x in d),losses=sum(x<0 for x in d),
        mean_paired_success_difference=statistics.mean(d) if d else None,
        case_bootstrap_95_percentile=interval,paired_rows=pairs,
        caveat='Small descriptive case bootstrap, not task-population CI or sequential significance test.')


def summarize(rows):
    if len(rows)!=24 or len({(r['case'],r['arm']) for r in rows})!=24 or set(r['case'] for r in rows)!=set(range(8)):
        raise ValueError('complete planned denominator required')
    for case in range(8):
        block=[r for r in rows if r['case']==case]
        if {r['arm'] for r in block}!=set(ARMS) or len({r['task'] for r in block})!=1:raise ValueError('paired case identity')
    groups=[]
    for task in TASKS:
        for arm in ARMS:
            sub=[r for r in rows if r['task']==task and r['arm']==arm]
            if len(sub)!=4:raise ValueError('task balance')
            scores=[r['score'] for r in sub if r['repair_success'] is True]
            groups.append(dict(task=task,arm=arm,planned=4,success=sum(r['repair_success'] is True for r in sub),
                known_failure=sum(r['repair_success'] is False for r in sub),unknown=sum(r['repair_success'] is None for r in sub),
                conservative_success_fraction=sum(r['repair_success'] is True for r in sub)/4,
                conditional_score_median=statistics.median(scores) if scores else None,
                conditional_score_sample_sd=statistics.stdev(scores) if len(scores)>1 else None,
                api_cost_usd=sum(r.get('cost_usd') or 0 for r in sub),
                generation_seconds=sum(r.get('generation_seconds') or 0 for r in sub),
                execution_wall_seconds=sum(r.get('execution_wall_seconds') or 0 for r in sub)))
    comps=[comparison(rows,'retrieved_repair',other) for other in ('no_external_memory','random_repair')]
    task_comps=[dict(task=task,**comparison([r for r in rows if r['task']==task],'retrieved_repair',other))
        for task in TASKS for other in ('no_external_memory','random_repair')]
    gate=all(c['unknown_pairs']==0 and c['wins']>c['losses'] for c in comps) and all(c['wins']>=c['losses'] for c in task_comps)
    return dict(role='T1_same_execution_allowance_repair_transfer_not_wallclock_e2e',groups=groups,
        comparisons=comps,task_comparisons=task_comps,development_expansion_gate=gate,
        caveats=['Eight old-development failed states, not a new untouched test cohort or eight full searches.',
                 'Primary success is zero-error execution plus valid-format scored submission, not clean-learning proof.',
                 'One call and 300-second execution allowance per arm; not equal realized cost or strict combined walltime.',
                 'Same-source-task memories, not cross-task transfer; random and retrieved may select identical examples.',
                 'No claim of novelty, stable generality, critic gain, scaling, or full-search improvement.'])


def main():
    p=checked();generation=read(ROOT/'generation-finished.json')
    if not generation['complete']:raise ValueError('generation incomplete; stop without effectiveness claim')
    observed={};proof={}
    for block in (0,1):
        work,spec=gpu_checked(block);finish=read(work/'execution-finished.json');launch=read(work/'launch.json')
        if finish['job']!=launch['job']:raise ValueError('job identity')
        proof[str(work/'execution-finished.json')]=sha((work/'execution-finished.json').read_bytes())
        for row in spec['rows']:
            path=work/f'result-{row["local_index"]}.json'
            if not path.exists():continue
            result=read(path)
            if (result['index'],result['code_sha256'],result['task'],result['job'])!=(row['local_index'],row['code_sha256'],row['task'],launch['job']):raise ValueError('result binding')
            observed[row['index']]=result;proof[str(path)]=sha(path.read_bytes())
    rows=[]
    for item in p['rows']:
        gen=read(ROOT/f'generated-{item["index"]}.json');r=observed.get(item['index'])
        if gen['status']!='generated':success=False;status='generation_'+gen['status']
        elif r is None:success=None;status='not_executed'
        elif r['status']=='infrastructure_error':success=None;status=r['status']
        else:success=r['status']=='valid';status=r['status']
        if success and (r.get('valid') is not True or not math.isfinite(r['score'])):raise ValueError('invalid success')
        rows.append(dict(index=item['index'],case=item['case'],task=item['task'],arm=item['arm'],seed=item['seed'],
            repair_success=success,status=status,score=r['score'] if success else None,
            cost_usd=gen.get('cost_usd'),generation_seconds=gen['seconds'],execution_wall_seconds=r.get('wall_seconds') if r else None,
            generated_code_sha256=gen.get('code_sha256'),target_code_sha256=item['target_code_sha256'],
            memory_diff_sha256=item['memory_diff_sha256'],job=r['job'] if r else None,source_tree=p['source_tree'],commit=p['commit']))
    result=summarize(rows);result.update(utc=now(),prepared_sha256=sha((ROOT/'prepared.json').read_bytes()),
        rows=rows,proof=proof,billing=public_budget(budget_module().snapshot(ROOT/'paid.sqlite')))
    digest=dump(ROOT/'summary.json',result)
    with (ROOT/'runs.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    dump(ROOT/'readout-finished.json',dict(utc=now(),summary_sha256=digest,csv_sha256=sha((ROOT/'runs.csv').read_bytes())))
    print(json.dumps(dict(summary_sha256=digest,groups=result['groups'],comparisons=result['comparisons'],
        development_expansion_gate=result['development_expansion_gate'],billing=result['billing'])))


if __name__=='__main__':main()
