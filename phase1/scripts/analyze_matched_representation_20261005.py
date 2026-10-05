"""One final exploratory readout, after all assigned programs have closed."""
import csv,json,math,os,statistics,subprocess
from pathlib import Path
from matched_representation_20261005 import R,B,TASKS,read,write,sha,load,check,schedule

def independent(task,prediction,spec):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    manifest=B/spec['view']/'manifest.json';assert sha(manifest)==spec['view_sha']
    labels=B/spec['source']/'private/dsearch.csv';assert sha(labels)==read(manifest)['source_dsearch_sha256']
    with labels.open(newline='',encoding='utf-8-sig') as f:truth=list(csv.DictReader(f))
    with prediction.open(newline='',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    p={r[spec['id']]:r for r in rows}
    assert len(p)==len(rows)==len(truth) and set(p)=={r[spec['id']] for r in truth}
    if task==TASKS[0]:
        return float(roc_auc_score([int(r[spec['label']]) for r in truth],[float(p[r[spec['id']]][spec['label']]) for r in truth]))
    values=np.array([float(p[r['id']][r['author']]) for r in truth]);assert np.isfinite(values).all()
    return float(-np.log(np.maximum(values,1e-15)).mean())

def main():
    plan=check();job=read(R/'launch.json')['job'];env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip(),'still running'
    account=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines()
    assert len(account)==1
    jid,state,elapsed,tres,exitcode,*_=account[0].split('|');assert jid==job and 'gres/gpu=2' in tres
    assert state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'))
    out=R/'readout-v1';assert not out.exists();out.mkdir(mode=0o700)
    rows=[];errors=[];receipts={}
    # Snapshot all output hashes before opening any dev labels.
    freeze={str(p.relative_to(R)):sha(p) for p in R.glob('episode-*/action-0/*') if p.is_file() and p.name in ('receipt.json','submission.csv','progress.json')}
    write(out/'prediction-freeze.json',freeze)
    for s in schedule():
        i=s['index'];ep=R/f'episode-{i}';act=ep/'action-0';done=read(ep/'completed.json') if (ep/'completed.json').exists() else {}
        row=dict(**s,completed=bool(done),valid=False,dev_metric=None,metric='auc' if s['task']==TASKS[0] else 'log_loss',
            selected_C=None,selected_ngram=None,selected_min_df=None,selected_inner=None,selected_converged=None,final_converged=None,
            grid_fits=None,binary_fits=None,seconds=done.get('seconds'),prediction_sha256=None,inner_split_sha256=None,
            feature_count=None,train_rows=None,query_rows=None,source_commit=plan['source_commit'],error_type=done.get('error_type'),versions=None)
        if done.get('valid') and (ep/'closed.json').exists() and read(ep/'closed.json')['returncode']==0:
            rec=read(act/'receipt.json');receipts[i]=rec;assert rec['grid_complete'] and len(rec['rows'])==28
            assert rec['task']==s['task'] and rec['arm']==s['arm'] and rec['seed']==s['seed']
            assert rec['grid']==plan['grid'] and [r['params'] for r in rec['rows']]==plan['grid']
            chosen=max(rec['rows'],key=lambda r:r['inner_oriented_score']);assert chosen==rec['selected']
            assert rec['classifier_fits']==29 and rec['features']<=50000
            assert rec['submission_sha256']==sha(act/'submission.csv')
            cfg=read(R/'configs'/f'{i}.json');scorer=Path(cfg['task']['search_only_dev_scorer_path'])
            assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256'];m=load('matched_scorer',scorer)
            score=m.score(s['task'],act/'submission.csv');v=score[row['metric']]
            v2=independent(s['task'],act/'submission.csv',m.SPEC[s['task']]);err=abs(v-v2);assert err<1e-12;errors.append(err)
            row.update(valid=True,dev_metric=v,selected_C=chosen['params']['C'],selected_ngram=chosen['params']['ngram'],
                selected_min_df=chosen['params']['min_df'],selected_inner=chosen['inner_oriented_score'],selected_converged=chosen['converged'],
                final_converged=rec['final_converged'],grid_fits=28,binary_fits=rec['binary_fits'],prediction_sha256=rec['submission_sha256'],
                inner_split_sha256=rec['inner_split_sha256'],feature_count=rec['features'],train_rows=rec['train_rows'],query_rows=rec['query_rows'],
                versions=json.dumps(rec['versions'],sort_keys=True))
        rows.append(row)
    contrasts=[];per_task=[]
    for task in TASKS:
        for seed in sorted({r['seed'] for r in rows}):
            pair={r['arm']:r for r in rows if r['task']==task and r['seed']==seed};a=pair['word'];b=pair['word_char'];complete=a['valid'] and b['valid']
            if complete:assert a['inner_split_sha256']==b['inner_split_sha256'] and a['versions']==b['versions']
            d=(b['dev_metric']-a['dev_metric'])*(1 if task==TASKS[0] else -1) if complete else None
            contrasts.append(dict(task=task,seed=seed,complete=complete,word_char_minus_word_oriented=d,
                inner_oriented_difference=b['selected_inner']-a['selected_inner'] if complete else None,
                seconds_difference=b['seconds']-a['seconds'] if complete else None))
        values=[c['word_char_minus_word_oriented'] for c in contrasts if c['task']==task and c['complete']]
        per_task.append(dict(task=task,complete_pairs=len(values),median=statistics.median(values) if values else None,
            sample_variance=statistics.variance(values) if len(values)>1 else None))
    for rel,h in freeze.items():assert sha(R/rel)==h
    all_complete=all(r['valid'] for r in rows)
    report=dict(protocol=plan['protocol'],source_commit=plan['source_commit'],plan_sha256=sha(R/'plan.json'),
        analysis_sha256=sha(__file__),job=job,allocation_state=state,exit_code=exitcode,
        allocation_seconds=int(elapsed),allocated_gpu_hours=2*int(elapsed)/3600,
        assigned=8,complete=sum(r['valid'] for r in rows),grid_classifier_fits_completed=sum(r['grid_fits'] or 0 for r in rows),
        classifier_fits_completed=sum(r['grid_fits']+1 for r in rows if r['valid']),binary_fits_completed=sum(r['binary_fits'] or 0 for r in rows),
        independent_scores=len(errors),max_absolute_verifier_error=max(errors,default=None),
        contrasts=contrasts,per_task=per_task,
        exploratory_gate=all_complete and all(r['selected_converged'] and r['final_converged'] for r in rows) and all(c['word_char_minus_word_oriented']>0 for c in contrasts),
        automatic_expansion=False,new_method_confirmed=False,protected_opened=False,
        limitation=plan['limitations']+' '+plan['budget'])
    write(out/'summary.json',report)
    with (out/'runs.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # Public internal-score curve summaries contain no text, labels, or per-example predictions.
    write(out/'inner-grid.json',{str(i):dict(arm=r['arm'],task=r['task'],seed=r['seed'],rows=r['rows'],selected=r['selected'],versions=r['versions']) for i,r in receipts.items()})
    write(out/'export-receipt.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(report))

if __name__=='__main__':main()
