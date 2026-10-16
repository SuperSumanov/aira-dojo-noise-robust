"""Closed8 program mechanism readout; never infer E2E or kernel concurrency."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,sort_keys=True,indent=2,allow_nan=False)
def effects(rows):
    out=[]
    for program in range(2):
        r=[x for x in rows if x['program']==program]
        if len(r)!=4 or not all(x.get('valid') and x.get('score') is not None and x.get('steps') is not None for x in r):
            out.append(dict(program=program,complete=False));continue
        a=[x for x in r if x['mode']=='solo'];b=[x for x in r if x['mode']=='colocated']
        assert len(a)==len(b)==2
        sign=1 if program==0 else -1
        av=[x['score']*sign for x in a];bv=[x['score']*sign for x in b]
        out.append(dict(program=program,complete=True,
            solo_steps=[x['steps'] for x in a],colocated_steps=[x['steps'] for x in b],
            solo_scores=[x['score'] for x in a],colocated_scores=[x['score'] for x in b],
            median_step_delta=statistics.median(x['steps'] for x in b)-statistics.median(x['steps'] for x in a),
            oriented_mean_score_delta=statistics.mean(bv)-statistics.mean(av),
            all_colocated_steps_lower=max(x['steps'] for x in b)<min(x['steps'] for x in a),
            all_colocated_scores_worse=max(bv)<min(av),
            all_colocated_scores_better=min(bv)>max(av),
            solo_score_repeat_span=max(av)-min(av),colocated_score_repeat_span=max(bv)-min(bv)))
    return out
def predictions(path):
    with Path(path).open(newline='') as f:
        rd=csv.DictReader(f);assert rd.fieldnames[0]=='id' and len(rd.fieldnames)==2
        rows=list(rd);ids=[r['id'] for r in rows];v=[float(r[rd.fieldnames[1]]) for r in rows]
    assert len(set(ids))==len(ids) and all(math.isfinite(x) for x in v)
    return ids,v
def analyze(root,out,seconds):
    root,out=Path(root),Path(out);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert 0<seconds<=2700 and p['gpus']==1 and p['allocation_seconds']==2700
    assert len(p['schedule'])==8 and closed['planned']==8
    for n,h in p['files'].items():assert sha(root/n)==h
    donor=Path('/research/d7/spc/yzyang4/scheduling-pooling-20261016-v3')
    assert sha(donor/'plan.json')==p['donor_plan_sha256']
    for n,h in p['donor_files'].items():assert sha(donor/n)==h
    sys.path.insert(0,str(donor))
    from image_dev_data_20261011 import score_at
    spec=read(donor/'dev-views/spec.json');native=read(root/'native.json')
    recs={x['index']:x for x in closed['records']};rows=[];recomputed=0;binds=[];traces={}
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
            binds.append(dict(index=i,gpu_uuid=b['gpu_uuid'],namespace=True))
        if row['started']:assert read(ep/'started.json')['cpu_affinity']==native['cpu_slots'][s['program']]
        if tr is not None:
            intervals=tr['host_step_intervals'];assert len(intervals)==tr['steps']
            cuda=[x for x in intervals if any(d.startswith('cuda:') for d in x['devices']) and x['gradient_parameters']>0]
            assert len(cuda)==tr['cuda_gradient_steps']
            traces[i]=(min(x['start'] for x in cuda),max(x['end'] for x in cuda)) if cuda else None
        rows.append(row)
    overlaps=[]
    for block in (1,2):
        a,b=traces.get(2*block),traces.get(2*block+1)
        overlap=None if not a or not b else max(0,min(a[1],b[1])-max(a[0],b[0]))
        overlaps.append(dict(block=block,host_training_envelope_overlap_seconds=overlap))
    pairs=[]
    for program in (0,1):
        eligible=[r for r in rows if r['program']==program and r['prediction_sha256']]
        for pos,a in enumerate(eligible):
            ai,av=predictions(root/f"episode-{a['index']}/prediction.private.csv")
            for b in eligible[pos+1:]:
                bi,bv=predictions(root/f"episode-{b['index']}/prediction.private.csv");assert ai==bi
                dif=[abs(x-y) for x,y in zip(av,bv)]
                pairs.append(dict(program=program,a=a['index'],b=b['index'],same_mode=a['mode']==b['mode'],
                    same_bytes=a['prediction_sha256']==b['prediction_sha256'],max_abs_diff=max(dif),mean_abs_diff=statistics.mean(dif)))
    assert not set(native['cpu_slots'][0])&set(native['cpu_slots'][1])
    result=dict(planned=8,complete=sum(r['complete'] for r in rows),valid=sum(r['valid'] for r in rows),
        recomputed=recomputed,gpu_seconds=seconds,gpu_hours=seconds/3600,source_commit=p['source_commit'],
        plan_sha256=sha(root/'plan.json'),reader_sha256=sha(__file__),effects=effects(rows),overlaps=overlaps,
        structure=bool(not closed['error'] and closed['cleanup_verified'] and all(r['complete'] for r in rows)
            and {r['index'] for r in binds}==set(range(8))),
        boundary='Two chronologically selected previously valid clock-guard programs, same training seed. Only2 pool repeats, known DEV data; no E2E/generalization or CUDA-kernel-overlap claim. All8 retained; invalid outputs are not zero-valued scores.')
    out.mkdir();write(out/'runs.json',rows);write(out/'prediction-differences.json',pairs);write(out/'summary.json',result)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('root');a.add_argument('out');a.add_argument('--gpu-seconds',type=int,required=True)
    v=a.parse_args();analyze(v.root,v.out,v.gpu_seconds)
