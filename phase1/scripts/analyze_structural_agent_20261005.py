"""Frozen full-denominator external development readout, after allocation closes."""
import csv,json,os,statistics,subprocess,sys
from pathlib import Path
from structural_agent_20261005 import R,B,PREV,c,read,write,sha,load,check
def independent(task,pred,spec):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    manifest=B/spec['view']/'manifest.json';assert sha(manifest)==spec['view_sha']
    label=B/spec['source']/'private/dsearch.csv';assert sha(label)==read(manifest)['source_dsearch_sha256']
    with label.open(newline='',encoding='utf-8-sig') as f:ys=list(csv.DictReader(f))
    with pred.open(newline='',encoding='utf-8-sig') as f:ps=list(csv.DictReader(f))
    pp={r[spec['id']]:r for r in ps};assert len(pp)==len(ps)==len(ys) and set(pp)=={r[spec['id']] for r in ys}
    if task==c.TASKS[0]:return float(roc_auc_score([int(r[spec['label']]) for r in ys],[float(pp[r[spec['id']]][spec['label']]) for r in ys]))
    return float(-np.log(np.maximum([float(pp[r['id']][r['author']]) for r in ys],1e-15)).mean())
def main():
    p=check();job=read(R/'launch.json')['job'];env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip()
    raw=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines();assert len(raw)==1
    jid,state,elapsed,tres,exitcode,*_=raw[0].split('|');assert jid==job and 'gres/gpu=4' in tres and state.startswith(('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'))
    out=R/'readout-v1';out.mkdir(mode=0o700)
    freezes={str(f.relative_to(R)):sha(f) for f in R.glob('episode-*/final/submission.csv')};write(out/'prediction-freeze.json',freezes)
    rows=[];errs=[]
    for s in c.schedule():
        i=s['index'];ep=R/f'episode-{i}';done=read(ep/'completed.json') if (ep/'completed.json').exists() else {}
        row={**s,'attempted':(ep/'native.json').exists(),'complete':False,'dev_metric':None,
            'selected':done.get('selected'),'initial_inner':done.get('initial_inner'),'selected_inner':done.get('selected_inner'),
            'proposal_valid':done.get('proposal_valid'),'proposal_inner':done.get('proposal_inner'),'inner_trials':done.get('inner_trials'),
            'grid_complete':done.get('grid_complete'),'generation_seconds':done.get('generation_seconds'),
            'search_seconds':done.get('search_seconds'),'refit_seconds':done.get('refit_seconds'),'elapsed_seconds':done.get('elapsed_seconds'),
            'error_type':done.get('error_type'),'proposal_error':done.get('proposal_error'),'generation_error':done.get('generation_error'),
            'prediction_sha256':None,'source_commit':p['source_commit']}
        if done.get('valid') and (ep/'closed.json').exists() and read(ep/'closed.json')['returncode']==0:
            pred=ep/'final/submission.csv';assert sha(pred)==done['prediction_sha256']
            cfg=read(R/'configs'/f'{i}.json');scorer=Path(cfg['task']['search_only_dev_scorer_path']);assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
            m=load('structural_scorer',scorer);rec=m.score(s['task'],pred);metric='auc' if s['task_index']==0 else 'log_loss';v=rec[metric]
            err=abs(v-independent(s['task'],pred,m.SPEC[s['task']]));assert err<1e-12;errs.append(err)
            row.update(complete=True,dev_metric=v,prediction_sha256=sha(pred))
        rows.append(row)
    contrasts=[];bytask=[]
    for task in c.TASKS:
        for seed in c.SEEDS:
            group={r['arm']:r for r in rows if r['task']==task and r['seed']==seed};complete=all(r['complete'] for r in group.values())
            sign=1 if task==c.TASKS[0] else -1;vals=[r['initial_inner'] for r in group.values() if r['initial_inner'] is not None]
            if vals:assert max(vals)-min(vals)<1e-12,'common parent drift'
            contrast=dict(task=task,seed=seed,complete=complete)
            for arm in ('ordinary','open_hpo'):contrast['profile_minus_'+arm]=sign*(group['profile']['dev_metric']-group[arm]['dev_metric']) if complete else None
            contrast['ordinary_minus_open_hpo']=sign*(group['ordinary']['dev_metric']-group['open_hpo']['dev_metric']) if complete else None
            contrasts.append(contrast)
        for key in ('profile_minus_ordinary','profile_minus_open_hpo','ordinary_minus_open_hpo'):
            v=[r[key] for r in contrasts if r['task']==task and r['complete']]
            bytask.append(dict(task=task,contrast=key,n=len(v),median=statistics.median(v) if v else None,sample_variance=statistics.variance(v) if len(v)>1 else None))
    for n,h in freezes.items():assert sha(R/n)==h
    result=dict(protocol=p['protocol'],source_commit=p['source_commit'],plan_sha256=sha(R/'plan.json'),analysis_sha256=sha(__file__),
        job=job,state=state,exit_code=exitcode,allocation_seconds=int(elapsed),allocated_gpu_hours=4*int(elapsed)/3600,
        assigned=12,attempted=sum(r['attempted'] for r in rows),complete=sum(r['complete'] for r in rows),independent_scores=len(errs),max_abs_error=max(errs,default=None),
        service=read(R/'service-ready.json') if (R/'service-ready.json').exists() else None,
        contrasts=contrasts,per_task=bytask,
        gate=all(r['complete'] and r['profile_minus_ordinary']>0 and r['profile_minus_open_hpo']>0 for r in contrasts),
        automatic_expansion=False,protected_opened=False,limitation=p['limitation'])
    write(out/'summary.json',result)
    with (out/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(out/'export-receipt.json',{f.name:sha(f) for f in out.iterdir() if f.is_file()});print(json.dumps(result))
if __name__=='__main__':main()
