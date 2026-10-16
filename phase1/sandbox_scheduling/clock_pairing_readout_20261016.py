"""One closed readout: all16known programs, task best/median/SD and full cost."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
from clock_contention_readout_20261016 import read,sha,write


def quality(rows):
    by=[]
    for b in range(4):
        for task in range(2):
            r=[x for x in rows if x['block']==b and x['program']//2==task]
            valid=len(r)==2 and all(x['complete'] and x['valid'] and x['score'] is not None for x in r)
            v=[x['score'] for x in r] if valid else []
            by.append(dict(block=b,task_index=task,complete=valid,
                best=(max(v) if task==0 else min(v)) if v else None,
                median=statistics.median(v) if v else None,sample_sd=statistics.stdev(v) if v else None))
    contrasts=[]
    for rep,(a,b) in enumerate(((0,1),(3,2))):
        for t in range(2):
            x=next(r for r in by if r['block']==a and r['task_index']==t)
            y=next(r for r in by if r['block']==b and r['task_index']==t)
            good=x['complete'] and y['complete'];sign=1 if t==0 else -1
            contrasts.append(dict(repeat=rep,task_index=t,complete=good,
                oriented_best_delta=sign*(y['best']-x['best']) if good else None,
                oriented_median_delta=sign*(y['median']-x['median']) if good else None))
    gate=all(r['complete'] and r['oriented_best_delta']>=(.001 if r['task_index']==1 else -1e-12) for r in contrasts)
    return by,contrasts,gate


def analyze(root,out,seconds):
    root,out=Path(root),Path(out);plan=read(root/'plan.json');closed=read(root/'closed.json')
    assert 0<seconds<=plan['allocation_seconds']==3120 and plan['gpus']==1
    for n,h in plan['files'].items():assert sha(root/n)==h
    donor=root.parent/'scheduling-pooling-20261016-v3'
    assert sha(donor/'plan.json')==plan['donor_plan_sha256']
    for n,h in plan['donor_files'].items():assert sha(donor/n)==h
    sys.path.insert(0,str(donor))
    from image_dev_data_20261011 import score_at
    spec=read(donor/'dev-views/spec.json');native=read(root/'native.json')
    expected_order=[i for block in plan['groups'] for pair in block for i in pair]
    assert [r['index'] for r in closed['records']]==expected_order[:len(closed['records'])]
    recs={x['index']:x for x in closed['records']};rows=[];traces={};bound=set();recomputed=0
    for s in plan['schedule']:
        i=s['index'];ep=root/f'episode-{i}';f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        tr=read(ep/'gpu-training.json') if (ep/'gpu-training.json').exists() else None
        cl=recs.get(i,{})
        r=dict(s,seed=plan['programs'][s['program']]['seed'],source_commit=plan['source_commit'],
            executed_code_sha256=f.get('executed_sha256'),started=(ep/'started.json').exists(),
            complete=bool(f and not f['error'] and cl.get('returncode')==0 and cl.get('cleanup')),
            valid=f.get('valid',False),elapsed_seconds=f.get('elapsed_seconds'),exec_seconds=f.get('exec_seconds'),
            steps=None if tr is None else tr['steps'],cuda_gradient_steps=None if tr is None else tr['cuda_gradient_steps'],
            score=None,prediction_sha256=None)
        if r['complete']:assert r['executed_code_sha256']==plan['programs'][s['program']]['executed_sha256']
        if (ep/'score.json').exists():
            rec=read(ep/'score.json');actual=score_at(donor,spec,s['task'],ep/'prediction.private.csv');metric=spec[s['task']]['metric_name']
            assert abs(actual[metric]-rec[metric])<=1e-12 and actual['submission_sha256']==rec['submission_sha256']
            r.update(score=actual[metric],prediction_sha256=actual['submission_sha256']);recomputed+=1
        for p in ep.glob('binding-*.json'):
            binding=read(p);assert binding['namespace']['exact_device_namespace'] and binding['gpu_uuid']==native['gpu_uuids'][0]
            bound.add(i)
        if r['started']:assert read(ep/'started.json')['cpu_affinity']==native['cpu_slots'][s['program']]
        if tr is not None:
            calls=tr['host_step_intervals'];assert len(calls)==tr['steps']
            cuda=[x for x in calls if any(d.startswith('cuda:') for d in x['devices']) and x['gradient_parameters']>0]
            assert len(cuda)==tr['cuda_gradient_steps']
            if cuda:traces[i]=(min(x['start'] for x in cuda),max(x['end'] for x in cuda))
        rows.append(r)
    assert native['cpu_slots'][0]==native['cpu_slots'][2] and native['cpu_slots'][1]==native['cpu_slots'][3]
    assert not set(native['cpu_slots'][0])&set(native['cpu_slots'][1])
    overlaps=[]
    for b,groups in enumerate(plan['groups']):
        for group in groups:
            a,z=(traces.get(i) for i in group)
            overlaps.append(dict(block=b,indices=group,host_training_envelope_overlap_seconds=None if not(a and z) else max(0,min(a[1],z[1])-max(a[0],z[0]))))
    by,contrasts,qgate=quality(rows)
    structure=bool(not closed['error'] and closed['cleanup_verified'] and all(r['complete'] for r in rows) and bound==set(range(16)))
    gate=bool(structure and all(r['valid'] for r in rows) and recomputed==16 and qgate
        and all(x['host_training_envelope_overlap_seconds'] is not None and x['host_training_envelope_overlap_seconds']>0 for x in overlaps))
    result=dict(planned=16,complete=sum(r['complete'] for r in rows),valid=sum(r['valid'] for r in rows),recomputed=recomputed,
        structure=structure,predeclared_gate_met=gate,task_blocks=by,contrasts=contrasts,overlaps=overlaps,
        gpu_seconds=seconds,gpu_hours=seconds/3600,plan_sha256=sha(root/'plan.json'),reader_sha256=sha(__file__),
        source_commit=plan['source_commit'],reserved_seconds_per_condition=2*plan['block_reserved_seconds'],
        boundary='Known18819program cohort; same multiset, inputs, seeds,300s caps, CPU bindings and1460s reserved per matching condition. ABBA two repeats, not independent task generalization, closed-loop search gain, SchedMate comparison or new-method novelty.')
    out.mkdir();write(out/'runs.json',rows);write(out/'summary.json',result)
    with (out/'runs.csv').open('x') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result))


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('root');a.add_argument('out');a.add_argument('--gpu-seconds',type=int,required=True)
    v=a.parse_args();analyze(v.root,v.out,v.gpu_seconds)
