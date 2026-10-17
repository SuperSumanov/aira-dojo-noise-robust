"""Frozen descriptive readout; complete assigned denominator, no rescue rule."""
import argparse,csv,json,math,statistics,sys
from pathlib import Path
from clock_contention_20261016 import read,write,sha

MODES=('cnn0','cnn1','patch','multiscale')
def assessment(rows):
    contrasts=[]
    for fold in (0,1):
        for seed in (5221,5222):
            rr=[r for r in rows if r['fold']==fold and r['seed']==seed]
            complete=len(rr)==4 and {r['mode'] for r in rr}==set(MODES) and all(r['qualified'] for r in rr)
            values={r['mode']:r['score'] for r in rr} if complete else {}
            gains={m:values[m]-values['multiscale'] for m in MODES[:3]} if complete else {}
            contrasts.append(dict(fold=fold,seed=seed,qualified=complete,gains=gains,
                                  pass_gate=bool(complete and all(v>=.001 for v in gains.values()))))
    return contrasts

def analyze(root,out,gpu_seconds):
    root,out=Path(root),Path(out)
    p,cl,n=read(root/'plan.json'),read(root/'closed.json'),read(root/'native.json')
    assert len(p['schedule'])==cl['planned']==16 and p['gpus']==1 and p['allocation_seconds']==7200
    assert 0<gpu_seconds<=7200 and not out.exists()
    for name,h in p['files'].items():assert sha(root/name)==h
    sys.path.insert(0,str(root))
    from image_dev_data_20261011 import score_at
    rec={x['index']:x for x in cl['records']};assert len(rec)==len(cl['records'])
    rows=[];recomputed=0
    for s in p['schedule']:
        ep=root/f"episode-{s['index']}";f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        st=read(ep/'started.json') if (ep/'started.json').exists() else {}
        tr=read(ep/'training.safe.json') if (ep/'training.safe.json').exists() else {}
        bindings=[read(q) for q in ep.glob('binding-*.json')]
        record=rec.get(s['index'],{})
        complete=bool(f and not f.get('error') and record.get('returncode')==0 and record.get('cleanup'))
        binding_ok=bool(bindings) and all(q['namespace']['exact_device_namespace'] and q['gpu_uuid']==n['gpu_uuids'][0] for q in bindings)
        affinity_ok=st.get('cpu_affinity')==n['cpu_slots'][0]
        method_ok=False;extra={}
        if s['program']<2:method_ok=tr.get('cuda_gradient_steps',0)>0
        elif (ep/'work/pixel_training.json').is_file():
            extra=read(ep/'work/pixel_training.json')
            method_ok=bool(tr.get('cuda_gradient_steps')==0 and extra['model']==s['mode'] and extra['seed']==s['seed']
                and extra['features']==(9 if s['mode']=='patch' else 21) and extra['training_pixels']>0)
        value=pred_sha=None
        if (ep/'score.private.json').is_file():
            actual=score_at(root,read(root/f"views/spec-{s['fold']}.json"),s['task'],ep/'prediction.private.csv')
            stored=read(ep/'score.private.json')
            assert actual['submission_sha256']==stored['submission_sha256'] and abs(actual['rmse']-stored['rmse'])<1e-12
            value,pred_sha=actual['rmse'],actual['submission_sha256'];recomputed+=1
        qualified=bool(complete and f.get('valid') and f.get('exit_code')==0 and not f.get('timed_out',True)
                       and f.get('executed_sha256')==s['executed_sha256'] and binding_ok and affinity_ok and method_ok and value is not None)
        rows.append(dict(s,source_commit=p['source_commit'],budget_seconds=300,started=bool(st),complete=complete,
            qualified=qualified,score=value,prediction_sha256=pred_sha,exec_seconds=f.get('exec_seconds'),
            elapsed_seconds=f.get('elapsed_seconds'),cuda_steps=tr.get('cuda_gradient_steps'),
            feature_columns=extra.get('features'),fit_seconds=extra.get('fit_seconds'),
            binding_ok=binding_ok,affinity_ok=affinity_ok,method_ok=method_ok))
    effects=assessment(rows)
    structure=bool(not cl['error'] and cl['cleanup_verified'] and len(rec)==16 and all(r['qualified'] for r in rows))
    groups=[]
    for fold in (0,1):
        for mode in MODES:
            values=[r['score'] for r in rows if r['fold']==fold and r['mode']==mode and r['qualified']]
            groups.append(dict(fold=fold,mode=mode,n=len(values),median=statistics.median(values) if values else None,
                sample_sd=statistics.stdev(values) if len(values)>1 else None))
    summary=dict(planned=16,started=sum(r['started'] for r in rows),complete=sum(r['complete'] for r in rows),
        qualified=sum(r['qualified'] for r in rows),recomputed=recomputed,structure=structure,
        opportunity_gate=bool(structure and all(e['pass_gate'] for e in effects)),contrasts=effects,groups=groups,
        plan_sha256=sha(root/'plan.json'),source_commit=p['source_commit'],reader_sha256=sha(__file__),
        gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,limits=p['limits'],
        claim='Single-task classical candidate-family headroom only. No new method, generated-policy benefit, or independent multi-task confirmation.')
    out.mkdir();write(out/'runs.json',rows);write(out/'summary.json',summary)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(summary))

def selftest():
    rows=[dict(fold=f,seed=s,mode=m,score=.02 if m!='multiscale' else .018,qualified=True)
          for f in (0,1) for s in (5221,5222) for m in MODES]
    assert all(e['pass_gate'] for e in assessment(rows))
    rows[0]['qualified']=False
    assert not all(e['pass_gate'] for e in assessment(rows))
    rows[0]['qualified']=True;rows[-1]['score']=.0201
    assert not assessment(rows)[-1]['pass_gate']
    rows[-1]['score']=.02
    assert not assessment(rows)[-1]['pass_gate']
    assert not all(e['pass_gate'] for e in assessment(rows[:-1]))
    print(json.dumps(dict(readout_selftest=True,missing_not_imputed=True,tie_not_win=True,one_bad_cell_fails=True)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',nargs='?');p.add_argument('out',nargs='?');p.add_argument('--gpu-seconds',type=int);p.add_argument('--selftest',action='store_true');a=p.parse_args()
    if a.selftest:selftest()
    else:analyze(a.root,a.out,a.gpu_seconds)
