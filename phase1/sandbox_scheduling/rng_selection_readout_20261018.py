"""One immutable readout: seal selection before reading common audit scores.

All 32 executions count. This is a known-DEV fixed-library seed-transfer assay,
not independent held-out task generalization or adaptive agent search.
"""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
from clock_contention_20261016 import read,write,sha

MODES=('global','sampler','addressed')

def choices(rows):
    result=[]
    for t in (0,1):
        rr=[r for r in rows if r['program']//2==t]
        complete=len(rr)==12 and all(r['qualified'] for r in rr)
        by_mode={}
        if complete:
            sign=1 if t==0 else -1
            for mode in MODES:
                means={}
                for program in (2*t,2*t+1):
                    q=[r for r in rr if r['program']==program and r['mode']==mode]
                    assert sorted(r['seed'] for r in q)==[4101,4102]
                    means[program]=statistics.mean(sign*r['score'] for r in q)
                by_mode[mode]=dict(program=max(means,key=lambda k:(means[k],-k)),oriented_means=means)
        result.append(dict(task_index=t,qualified=complete,by_mode=by_mode))
    return result

def assessment(selected,audit):
    results=[]
    for c in selected:
        t=c['task_index'];rr=[r for r in audit if r['program']//2==t]
        complete=c['qualified'] and len(rr)==4 and all(r['qualified'] for r in rr)
        result=dict(task_index=t,qualified=complete,contrasts=[])
        if complete:
            sign=1 if t==0 else -1
            lookup={(r['program'],r['seed']):r['score'] for r in rr}
            programs={m:c['by_mode'][m]['program'] for m in MODES}
            result['chosen_programs']=programs
            for reference in MODES[:2]:
                deltas=[sign*(lookup[programs['addressed'],s]-lookup[programs[reference],s]) for s in (4103,4104)]
                result['contrasts'].append(dict(reference=reference,oriented_deltas=deltas,
                    median=statistics.median(deltas),sample_sd=statistics.stdev(deltas),
                    pass_gate=all(x>=(0 if t==0 else .001) for x in deltas)))
        results.append(result)
    return results

def analyze(root,out,gpu_seconds):
    root,out=Path(root),Path(out)
    p=read(root/'plan.json');cl=read(root/'closed.json');native=read(root/'native.json')
    assert len(p['schedule'])==cl['planned']==32
    assert p['gpus']==4 and p['allocation_seconds']==3600 and 0<gpu_seconds<=14400
    for name,h in p['files'].items():assert sha(root/name)==h
    donor=Path(p['donor_root']);runtime=Path(p['runtime_root'])
    assert sha(donor/'plan.json')==p['donor_plan_sha256']
    assert sha(runtime/'plan.json')==p['runtime_plan_sha256']
    for name,h in p['runtime_files'].items():assert sha(runtime/name)==h
    sys.path.insert(0,str(runtime))
    from image_dev_data_20261011 import score_at
    # Exact DEV content identity is already checked in preparation; recheck here.
    spec=read(donor/'dev-views/spec.json')
    recs={r['index']:r for r in cl['records']};assert len(recs)==len(cl['records'])
    out.mkdir();rows=[];inputs={};score_count=0
    def load(s):
        nonlocal score_count
        i=s['index'];ep=root/f'episode-{i}';f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        c=recs.get(i,{})
        tr=read(ep/'training.safe.json') if (ep/'training.safe.json').exists() else None
        binds=[read(q) for q in ep.glob('binding-*.json')]
        bindings_ok=bool(binds) and all(b['namespace']['exact_device_namespace'] and b['gpu_uuid']==native['gpu_uuids'][s['slot']] for b in binds)
        started=read(ep/'started.json') if (ep/'started.json').exists() else None
        affinity_ok=bool(started) and started['cpu_affinity']==native['cpu_slots'][s['slot']]
        complete=bool(f and not f.get('error') and c.get('returncode')==0 and c.get('cleanup'))
        row=dict(s,source_commit=p['source_commit'],started=bool(started),complete=complete,
            valid=f.get('valid',False),exec_seconds=f.get('exec_seconds'),elapsed_seconds=f.get('elapsed_seconds'),
            steps=None,cuda_gradient_steps=None,score=None,prediction_sha256=None,
            bindings_ok=bindings_ok,affinity_ok=affinity_ok,rng_applied=False,unused_training_loaders=None,qualified=False)
        if complete:assert f['executed_sha256']==s['executed_sha256']
        if tr:
            row['steps']=tr['steps'];row['cuda_gradient_steps']=tr['cuda_gradient_steps']
            intervals=tr['host_step_intervals'];assert len(intervals)==tr['steps']
            assert sum(any(d.startswith('cuda:') for d in x['devices']) and x['gradient_parameters']>0 for x in intervals)==tr['cuda_gradient_steps']
            logs=tr.get('data_rng',[])
            # A constructed but never iterated loader has no intervention event.
            # Require actual training iterations, not every unused object to run.
            row['rng_applied']=bool(logs) and all(l['mode']==s['mode'] and l['samples']>0 for l in logs) and any(l['epochs'] for l in logs)
            row['unused_training_loaders']=sum(not l['epochs'] for l in logs)
            inputs[str(i)]=[dict(loader=l['loader'],input_multiset_sha256=l['input_multiset_sha256'],samples=l['samples'],epochs=l['epochs']) for l in logs]
        if (ep/'score.private.json').exists():
            receipt=read(ep/'score.private.json')
            actual=score_at(donor,spec,s['task'],ep/'prediction.private.csv');metric=spec[s['task']]['metric_name']
            assert abs(actual[metric]-receipt[metric])<=1e-12
            assert actual['submission_sha256']==receipt['submission_sha256']
            row.update(score=actual[metric],prediction_sha256=receipt['submission_sha256']);score_count+=1
        row['qualified']=bool(complete and row['valid'] and not f.get('timed_out',True) and f.get('exit_code')==0 and
            row['score'] is not None and bindings_ok and affinity_ok and row['rng_applied'] and (row['cuda_gradient_steps'] or 0)>0)
        return row
    # Never inspect deployment scores until these 24 selection records and
    # deterministic decisions have been saved exclusively to a new directory.
    for s in p['schedule'][:24]:
        assert s['phase']=='selection';rows.append(load(s))
    selected=choices(rows)
    write(out/'selection-sealed.json',dict(plan_sha256=sha(root/'plan.json'),rows=rows,choices=selected))
    selection_sha=sha(out/'selection-sealed.json')
    for s in p['schedule'][24:]:
        assert s['phase']=='deployment';rows.append(load(s))
    effects=assessment(selected,rows[24:])
    structure=bool(not cl['error'] and cl['cleanup_verified'] and len(recs)==32 and all(r['qualified'] for r in rows))
    passed=bool(structure and all(e['qualified'] and all(c['pass_gate'] for c in e['contrasts']) for e in effects))
    summary=dict(planned=32,started=sum(r['started'] for r in rows),complete=sum(r['complete'] for r in rows),
        qualified=sum(r['qualified'] for r in rows),recomputed=score_count,structure=structure,quality_gate=passed,
        choices=selected,effects=effects,source_commit=p['source_commit'],plan_sha256=sha(root/'plan.json'),
        reader_sha256=sha(__file__),selection_seal_sha256=selection_sha,
        gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
        limitations=p['limits'],claim='Only fixed-library selection and seed transfer. Classical CRN, no novelty or adaptive-search/generalization proof.')
    write(out/'runs.json',rows);write(out/'rng-traces.json',inputs);write(out/'summary.json',summary)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(summary))

def selftest():
    rows=[]
    # Addressed and sampler choose the same candidate: no claimed extra gain.
    for t in (0,1):
        for mode in MODES:
            for seed in (4101,4102):
                for k in (0,1):
                    score=1-k*.01 if t==0 else .1+k*.01
                    rows.append(dict(program=2*t+k,mode=mode,seed=seed,score=score,qualified=True))
    c=choices(rows);audit=[]
    for t in (0,1):
        for k in (0,1):
            for s in (4103,4104):audit.append(dict(program=2*t+k,seed=s,score=.2+k*.01,qualified=True))
    e=assessment(c,audit)
    assert not any(x['pass_gate'] for x in e[1]['contrasts'])
    rows[0]['qualified']=False
    assert not choices(rows)[0]['qualified']
    c[1]['by_mode']['addressed']['program']=3
    assert all(x['oriented_deltas']==[-.010000000000000009]*2 for x in assessment(c,audit)[1]['contrasts'])
    print(json.dumps(dict(readout_selftest=True,missing_not_imputed=True,same_choice_no_positive=True)))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('root',nargs='?');a.add_argument('out',nargs='?')
    a.add_argument('--gpu-seconds',type=int);a.add_argument('--selftest',action='store_true');v=a.parse_args()
    if v.selftest:selftest()
    else:analyze(v.root,v.out,v.gpu_seconds)
