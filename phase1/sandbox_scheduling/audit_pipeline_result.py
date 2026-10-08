"""Independent CLOSED pipeline audit; no re-execution or raw-value export."""
from collections import Counter
import itertools
import json
from pathlib import Path
import statistics

from lifecycle_pilot import read,write,sha
from verify_pool_outputs import strict

R=Path('/research/d7/spc/yzyang4/scheduling-pipeline-20261008-v1')
PIN='e2496978a3d0d58870ac05d0d3283f238ada8963219b7b2252eab0f488f46094'


def main():
    if sha(R/'plan.json')!=PIN:raise ValueError('plan pin')
    plan=read(R/'plan.json');report=read(R/'readout-v1/summary.json');runs=read(R/'runs.json')
    for name,pin in plan['files'].items():
        if sha(R/name)!=pin:raise ValueError('source drift')
    for path,pin in plan['input_files'].items():
        if sha(path)!=pin:raise ValueError('input drift')
    if report['runs']!=runs or report['plan_sha256']!=PIN:raise ValueError('readout provenance')
    if [r['index'] for r in runs]!=list(range(36)) or Counter((r['program'],r['arm']) for r in runs)!=Counter({(p,a):3 for p in (0,1,4,3) for a in ('serial','pipeline','share2')}):raise ValueError('matrix')
    outputs={};affinities=set();devices=set();times={}
    for r in runs:
        ep=R/f'episode-{r["index"]}'
        if (ep/'started.json').exists():
            affinities.add(tuple(read(ep/'started.json')['affinity']))
            devices.add(tuple(read(ep/'native.json')['gpu_uuids']))
        if r['status']!='complete':continue
        done=read(ep/'completed.json');closed=read(ep/'closed.json')
        if not done['complete'] or closed['returncode']!=0:raise ValueError('completed status')
        output=ep/'work/submission.csv'
        if sha(output)!=done['output']['sha256'] or sha(output)!=r['output_sha256']:raise ValueError('output drift')
        outputs[r['index']]=strict(output)
        a=read(ep/'candidate_started.json')['time'];z=read(ep/'candidate_ended.json')['time']
        ready=read(ep/'prelude_ready.json')['time'];admit=read(ep/'execution_admitted.json')['time']
        if not done['start']<=ready<=admit<=a<=z<=done['end']<=closed['end']:raise ValueError('stage order')
        if r['arm']=='pipeline' and r['position']:
            prior=read(R/f'episode-{r["index"]-1}/closed.json')
            if prior['returncode']!=0 or prior['end']>admit:raise ValueError('pipeline close barrier')
        times[r['index']]=(a,z)
    allocation=read(R/'allocation.json')
    if len(affinities)!=1 or next(iter(affinities))!=tuple(allocation['affinity']) or devices!={(allocation['gpu_uuid'],)}:raise ValueError('resource identity')
    equality=[]
    for p in (0,1,4,3):
        own=[r for r in runs if r['program']==p]
        complete=all(r['index'] in outputs for r in own)
        equal=all(outputs[a['index']]==outputs[b['index']] for a,b in itertools.combinations(own,2)) if complete else None
        if complete and equal!=next(x['exact_numerical_equality'] for x in report['output_equivalence'] if x['program']==p):raise ValueError('numeric disagreement')
        equality.append(dict(program=p,completed_outputs=sum(r['index'] in outputs for r in own),exact_equality=equal))
    durations={}
    for b in range(9):
        path=R/f'block-{b}.json'
        if not path.exists():continue
        record=read(path);own=runs[4*b:4*b+4]
        spans=[times[r['index']] for r in own if r['index'] in times]
        if any(not record['start']<=a<=z<=record['end'] for a,z in spans):raise ValueError('block interval')
        if record['arm'] in ('serial','pipeline') and any(max(a,c)<min(z,d) for (a,z),(c,d) in itertools.combinations(spans,2)):raise ValueError('candidate overlap')
        if len(spans)==4:durations[record['repeat'],record['arm']]=record['end']-record['start']
    ratios={}
    for a,b in (('serial','pipeline'),('serial','share2'),('pipeline','share2')):
        pairs=[dict(repeat=k,ratio=durations[k,a]/durations[k,b]) for k in range(3) if (k,a) in durations and (k,b) in durations]
        if pairs!=report['ratios'][a+'_over_'+b]['pairs']:raise ValueError('timing disagreement')
        ratios[a+'_over_'+b]=dict(pairs=pairs,median=statistics.median(p['ratio'] for p in pairs) if pairs else None)
    result=dict(job=report['job'],plan_sha256=PIN,primary_sha256=sha(R/'readout-v1/summary.json'),
                full_denominator=36,completed=sum(r['status']=='complete' for r in runs),
                same_affinity_and_device=True,all_frozen_sources_and_inputs_match=True,
                pipeline_candidate_nonoverlap_verified=True,numerical=equality,ratios=ratios,
                no_quality_labels_read=True,no_raw_values_exported=True,
                boundary='Audit, not new observations. Three same-source restarts on a small fixed pool; no kernel concurrency or E2E claim.')
    dest=R/'audit-v1';dest.mkdir(mode=0o700,exist_ok=False);write(dest/'summary.json',result)
    print(json.dumps(dict(job=result['job'],completed=result['completed'],audit_sha256=sha(dest/'summary.json'),numerical=equality,ratios=ratios),sort_keys=True))


if __name__=='__main__':main()
