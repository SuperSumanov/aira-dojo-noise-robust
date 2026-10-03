"""Independent aggregate-only verification/export for the frozen six slots.

No fits, generation, labels/predictions in output, or modifications to originals.
"""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess

R=Path('/research/d7/spc/yzyang4/diagnostic-text-scope-20261004-v1')
PLAN='2606e7a3903b40c05453136e254a94f37e4cfadfb2e0890b81e03b6b3455d357'
SOURCE='3ac71cdc5278dd906906221cc5c19472ce95b1805f26f7b96333ae16f5eabe7b'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{10,}|hf_[a-z0-9]{15,}|gh[pousr]_[a-z0-9]{15,}|Bearer\s+\S{12,})')


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def read(p):
    raw=p.read_bytes();assert not SECRET.search(raw)
    return json.loads(raw)


def write(p,value):
    raw=(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
    assert not SECRET.search(raw)
    with p.open('xb') as f:f.write(raw)


def main():
    import numpy as np
    os.umask(0o077)
    assert sha(R/'plan.json')==PLAN
    assert sha(R/'diagnostic_scope_text_20261004.py')==SOURCE
    plan=read(R/'plan.json');summary=read(R/'readout-v1/summary.json')
    assert summary['plan_sha256']==PLAN and summary['script_sha256']==SOURCE
    closed=read(R/'closed.json');assert closed['plan_sha256']==PLAN
    assert len(closed['slots'])==6 and all(s['returncode']==0 and not s['supervisor_timeout'] for s in closed['slots'])
    job=read(R/'launch.json')['job'];assert job=='15851'
    checked=[];preds={};metadata={};native=[]
    for slot in plan['schedule']:
        i=slot['index'];d=R/f'episode-{i}/action-0'
        row=next(x for x in summary['rows'] if x['index']==i)
        receipt=read(d/'result.json')
        assert all(row[k]==v==receipt[k] for k,v in slot.items())
        assert receipt['plan_sha256']==PLAN and receipt['code_sha256']==sha(R/'programs'/f'{i}.private.py')
        n=read(R/f'episode-{i}/native.json');assert n['job']==job
        assert n['config_sha256']==sha(R/'configs'/f'{i}.json')
        native.append(n['gpu_uuids'])
        assert row['complete']==receipt['complete']
        if not row['complete']:
            checked.append(dict(index=i,complete=False,error=None));continue
        for name,h in receipt['artifacts'].items():assert sha(d/name)==h
        with np.load(d/'diagnostic_oof.npz',allow_pickle=False) as f:
            y=f['y'];p=f['predictions'];tr=f['train_indices'];va=f['val_indices']
        assert p.shape==(len(y),3) and set(y)=={0,1,2}
        assert np.isfinite(p).all() and (p>=0).all() and (p<=1).all()
        assert np.max(np.abs(p.sum(axis=1)-1))<1e-12
        assert len(set(tr)&set(va))==0 and len(set(tr))==len(tr) and len(set(va))==len(va)
        # Independent scalar implementation; no sklearn and no main readout helper.
        eps=float(np.finfo(p.dtype).eps)
        losses=[]
        for label,probs in zip(y,p):
            safe=[max(eps,min(1-eps,float(v))) for v in probs]
            losses.append(-math.log(safe[int(label)]/math.fsum(safe)))
        value=math.fsum(losses)/len(losses)
        err=abs(value-row['log_loss']);assert err<1e-12
        checked.append(dict(index=i,complete=True,error=err))
        preds[i]=(tr,va,y);metadata[i]=read(d/'diagnostic_meta.json')
    assert all(x==native[0] for x in native)
    controls=[];pairs=[]
    for seed in (42,173):
        group=[x for x in summary['rows'] if x['seed']==seed]
        a=next(x for x in group if x['arm']=='all_public')
        b=next(x for x in group if x['case']=='diagnostic' and x['arm']=='fold_train')
        r=next(x for x in group if x['case']=='reference')
        old=next(x for x in summary['pairs'] if x['seed']==seed)
        if all(x['complete'] for x in group):
            assert abs((a['log_loss']-b['log_loss'])-old['all_minus_fold'])<1e-12
            reverse=(a['log_loss']<r['log_loss'])!=(b['log_loss']<r['log_loss'])
            assert reverse==old['ranking_reversal']
            for arr in range(3):
                assert np.array_equal(preds[a['index']][arr],preds[b['index']][arr]) and np.array_equal(preds[b['index']][arr],preds[r['index']][arr])
            for key in ('matrix_train_sha256','matrix_val_sha256','vocabulary_sha256','idf_sha256'):
                controls.append(dict(seed=seed,field=key,passed=metadata[b['index']][key]==metadata[r['index']][key]))
        pairs.append(old)
    assert all(x['passed'] for x in controls)==(not summary['controls'])
    reproduction=[]
    for case,key in [('diagnostic','original_singlefold_rounded'),('reference','original_reference_rounded')]:
        r=next(x for x in summary['rows'] if x['case']==case and x['seed']==42 and (case=='reference' or x['arm']=='all_public'))
        passed=None if not r['complete'] else abs(r['log_loss']-plan[key])<=5e-7
        assert passed==next(x for x in summary['reproduction'] if x['case']==case)['passed']
        reproduction.append(dict(case=case,passed=passed))
    env=os.environ.copy();env['SLURM_CONF']='/opt1/slurm/gpu-slurm.conf'
    accounting=subprocess.check_output(['sacct','-X','-j',job,'--noheader','--parsable2','--format=JobIDRaw,State,ElapsedRaw,AllocTRES,NodeList,ExitCode'],env=env,text=True,timeout=20).strip()
    parts=accounting.split('|');assert len(parts)>=6 and parts[0]==job and parts[1]=='COMPLETED' and parts[4]=='gpu3'
    match=re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',parts[3]);assert match and int(match.group(1))==1
    resources=dict(job=job,accounting=accounting,allocation_seconds=int(parts[2]),gpus=1,gpu_hours=int(parts[2])/3600,
                   paid_api=0,generator_calls=0,base_model_updates=0)
    assert resources['gpu_hours']<=.75
    out=R/'verified-export-v1';assert not out.exists();out.mkdir()
    verification=dict(status='VERIFIED_READOUT',scientific_status=summary['status'],plan_sha256=PLAN,source_sha256=SOURCE,
        verifier_sha256=sha(Path(__file__)),assigned=6,completed=sum(x['complete'] for x in checked),
        scalar_metric_checks=checked,feature_scope_controls=controls,reproduction=reproduction,
        scope='Verification of this closed replay, not an effect/generalization gate. Incomplete/reproduction/control failures retained. No endpoint-agent benefit inferred.')
    write(out/'verification.json',verification);write(out/'resources.json',resources)
    for name,src in [('summary.aggregate.json',R/'readout-v1/summary.json'),('runs.csv',R/'readout-v1/runs.csv'),('launch.json',R/'launch.json'),('cpu.json',R/'cpu.json'),('analysis-freeze.json',R/'analysis-freeze.json')]:
        assert not SECRET.search(src.read_bytes());shutil.copyfile(src,out/name)
    safe={k:v for k,v in plan.items() if k not in ('files','original_singlefold_rounded','original_reference_rounded')}
    safe['original_plan_sha256']=PLAN;write(out/'plan.aggregate.json',safe)
    with (out/'pairs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
    write(out/'export-receipt.json',dict(source_root=str(R),plan_sha256=PLAN,summary_sha256=sha(R/'readout-v1/summary.json'),
          verifier_sha256=sha(Path(__file__)),payloads={p.name:sha(p) for p in out.iterdir() if p.is_file()},
          raw_predictions_exported=False,raw_labels_exported=False,raw_candidates_exported=False))
    print(json.dumps(dict(status=verification['status'],scientific_status=summary['status'],assigned=6,complete=verification['completed'],resources=resources,
        controls=controls,reproduction=reproduction,summary_sha256=sha(R/'readout-v1/summary.json'),receipt_sha256=sha(out/'export-receipt.json'))))


if __name__=='__main__':main()
