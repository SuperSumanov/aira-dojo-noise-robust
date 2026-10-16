"""Closed16 rank mechanism: full denominator, both repeats, no E2E claim."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
from clock_contention_readout_20261016 import read,sha,write

def ranking(rows):
    out=[]
    for task_index in (0,1):
        selected=[r for r in rows if r['program']//2==task_index]
        if len(selected)!=8 or not all(r['complete'] and r['valid'] and r['score'] is not None for r in selected):
            out.append(dict(task_index=task_index,complete=False));continue
        sign=1 if task_index==0 else -1
        margins=[]
        for b in range(4):
            pair=sorted((r for r in selected if r['block']==b),key=lambda r:r['program'])
            assert len(pair)==2
            margins.append(sign*(pair[0]['score']-pair[1]['score']))
        order=lambda x:1 if x>0 else -1 if x<0 else 0
        by_mode={}
        for mode in ('solo','colocated'):
            pair=[[sign*r['score'] for r in selected if r['mode']==mode and r['program']==p] for p in (2*task_index,2*task_index+1)]
            assert all(len(v)==2 for v in pair)
            by_mode[mode]=1 if min(pair[0])>max(pair[1]) else -1 if max(pair[0])<min(pair[1]) else 0
        out.append(dict(task_index=task_index,complete=True,block_oriented_first_minus_second=margins,
            within_repeat_flip=[order(margins[0])*order(margins[1])==-1,order(margins[3])*order(margins[2])==-1],
            solo_same_order=order(margins[0])==order(margins[3])!=0,
            colocated_same_order=order(margins[1])==order(margins[2])!=0,
            interval_separated_order=by_mode,
            strict_repeated_flip=by_mode['solo']*by_mode['colocated']==-1))
    return out

def analyze(root,out,seconds):
    root,out=Path(root),Path(out);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert 0<seconds<=5400 and p['gpus']==1 and p['allocation_seconds']==5400
    assert len(p['schedule'])==16 and closed['planned']==16
    for n,h in p['files'].items():assert sha(root/n)==h
    donor=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261016-v3')
    assert sha(donor/'plan.json')==p['donor_plan_sha256']
    for n,h in p['donor_files'].items():assert sha(donor/n)==h
    sys.path.insert(0,str(donor))
    from image_dev_data_20261011 import score_at
    spec=read(donor/'dev-views/spec.json');native=read(root/'native.json')
    recs={x['index']:x for x in closed['records']};rows=[];recomputed=0;bound=set();traces={}
    for s in p['schedule']:
        i=s['index'];ep=root/f'episode-{i}';f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        tr=read(ep/'gpu-training.json') if (ep/'gpu-training.json').exists() else None
        cl=recs.get(i,{})
        row=dict(s,seed=p['programs'][s['program']]['seed'],source_commit=p['source_commit'],
            executed_code_sha256=f.get('executed_sha256'),started=(ep/'started.json').exists(),
            complete=bool(f and not f['error'] and cl.get('returncode')==0 and cl.get('cleanup')),
            valid=f.get('valid',False),elapsed_seconds=f.get('elapsed_seconds'),exec_seconds=f.get('exec_seconds'),
            steps=None if tr is None else tr['steps'],cuda_gradient_steps=None if tr is None else tr['cuda_gradient_steps'],
            score=None,prediction_sha256=None)
        if row['complete']:assert row['executed_code_sha256']==p['programs'][s['program']]['executed_sha256']
        if (ep/'score.json').exists():
            rec=read(ep/'score.json');actual=score_at(donor,spec,s['task'],ep/'prediction.private.csv')
            metric=spec[s['task']]['metric_name'];assert abs(actual[metric]-rec[metric])<=1e-12
            assert actual['submission_sha256']==rec['submission_sha256']
            row.update(score=actual[metric],prediction_sha256=rec['submission_sha256']);recomputed+=1
        for q in ep.glob('binding-*.json'):
            b=read(q);assert b['namespace']['exact_device_namespace'] and b['gpu_uuid']==native['gpu_uuids'][0]
            bound.add(i)
        if row['started']:assert read(ep/'started.json')['cpu_affinity']==native['cpu_slots'][s['program']]
        if tr is not None:
            intervals=tr['host_step_intervals'];assert len(intervals)==tr['steps']
            cuda=[x for x in intervals if any(d.startswith('cuda:') for d in x['devices']) and x['gradient_parameters']>0]
            assert len(cuda)==tr['cuda_gradient_steps']
            traces[i]=(min(x['start'] for x in cuda),max(x['end'] for x in cuda)) if cuda else None
        rows.append(row)
    assert native['cpu_slots'][0]==native['cpu_slots'][2] and native['cpu_slots'][1]==native['cpu_slots'][3]
    assert not set(native['cpu_slots'][0])&set(native['cpu_slots'][1])
    overlaps=[]
    for block in (1,2):
        for task in (0,1):
            a,b=traces.get(4*block+2*task),traces.get(4*block+2*task+1)
            overlap=None if not a or not b else max(0,min(a[1],b[1])-max(a[0],b[0]))
            overlaps.append(dict(block=block,task_index=task,host_training_envelope_overlap_seconds=overlap))
    effects=[]
    for program in range(4):
        selected=[r for r in rows if r['program']==program]
        if len(selected)!=4 or not all(r['complete'] and r['valid'] and r['score'] is not None for r in selected):
            effects.append(dict(program=program,complete=False));continue
        a=[r for r in selected if r['mode']=='solo'];b=[r for r in selected if r['mode']=='colocated']
        sign=1 if program<2 else -1
        effects.append(dict(program=program,complete=True,solo_steps=[r['steps'] for r in a],
            colocated_steps=[r['steps'] for r in b],solo_scores=[r['score'] for r in a],colocated_scores=[r['score'] for r in b],
            oriented_mean_score_delta=sign*(statistics.mean(r['score'] for r in b)-statistics.mean(r['score'] for r in a))))
    result=dict(planned=16,complete=sum(r['complete'] for r in rows),valid=sum(r['valid'] for r in rows),
        recomputed=recomputed,gpu_seconds=seconds,gpu_hours=seconds/3600,source_commit=p['source_commit'],
        plan_sha256=sha(root/'plan.json'),reader_sha256=sha(__file__),effects=effects,overlaps=overlaps,ranking=ranking(rows),
        structure=bool(not closed['error'] and closed['cleanup_verified'] and all(r['complete'] for r in rows) and bound==set(range(16))),
        boundary='4 chronological known DEV programs (2 reused from18812),2 pool repeats. Strict interval-separated ranking reversal is descriptive, not significance or E2E/generalization. Host envelopes are not kernel overlap.')
    out.mkdir();write(out/'runs.json',rows);write(out/'summary.json',result)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('root');a.add_argument('out');a.add_argument('--gpu-seconds',type=int,required=True)
    v=a.parse_args();analyze(v.root,v.out,v.gpu_seconds)
