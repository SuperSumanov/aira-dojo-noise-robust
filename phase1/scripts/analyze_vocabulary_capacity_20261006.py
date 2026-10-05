"""Post-closure capacity ablation. No model fit, selected-seed rescue or old gate change."""
import csv
import json
import os
from pathlib import Path
import statistics
import subprocess

from vocabulary_capacity_20261006 import R, B, PREV, configure, runner, schedule, read, write, sha
from analyze_matched_representation_20261005 import independent

ARMS=('word','word_25k','word_char')
CONTRASTS=(('word_char','word_25k'),('word_25k','word'),('word_char','word'))


def paired(rows):
    out=[]
    for task in runner.TASKS:
        for seed in runner.SEEDS:
            group={r['arm']:r for r in rows if r['task']==task and r['seed']==seed}
            assert set(group)==set(ARMS)
            for b,a in CONTRASTS:
                valid=group[a]['valid'] and group[b]['valid']
                if valid:
                    assert group[a]['inner_split_sha256']==group[b]['inner_split_sha256']
                    assert group[a]['versions']==group[b]['versions']
                sign=1 if task==runner.TASKS[0] else -1
                out.append(dict(task=task,seed=seed,contrast=b+'_minus_'+a,complete=valid,
                    difference=sign*(group[b]['dev_metric']-group[a]['dev_metric']) if valid else None))
    return out


def conditional_intervals(rows):
    import numpy as np
    from scipy.stats import rankdata
    result=[];rng=np.random.default_rng(116399)
    for task in runner.TASKS:
        group=[r for r in rows if r['task']==task and r['valid']]
        if not group:continue
        cfg=read(R/'configs'/f"{group[0]['index']}.json")
        scorer=Path(cfg['task']['search_only_dev_scorer_path'])
        assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
        spec=runner.load('capacity_bootstrap_scorer',scorer).SPEC[task]
        manifest=B/spec['view']/'manifest.json';assert sha(manifest)==spec['view_sha']
        label_path=B/spec['source']/'private/dsearch.csv'
        assert sha(label_path)==read(manifest)['source_dsearch_sha256']
        with label_path.open(newline='',encoding='utf-8-sig') as f:labels=list(csv.DictReader(f))
        prediction={}
        for row in group:
            p=R/f"episode-{row['index']}"/'action-0/submission.csv';assert sha(p)==row['prediction_sha256']
            with p.open(newline='',encoding='utf-8-sig') as f:data=list(csv.DictReader(f))
            keyed={r[spec['id']]:r for r in data};assert len(keyed)==len(data)==len(labels)
            if task==runner.TASKS[0]:values=[float(keyed[r[spec['id']]][spec['label']]) for r in labels]
            else:values=[float(keyed[r['id']][r['author']]) for r in labels]
            prediction[(row['seed'],row['arm'])]=np.asarray(values)
        if task==runner.TASKS[0]:
            y=np.array([int(r[spec['label']]) for r in labels]);clusters={}
            for i,row in enumerate(labels):
                key=row['requester_username'];assert key and key not in ('None','nan');clusters.setdefault(key,[]).append(i)
            groups=[np.array(x) for x in clusters.values()]
            def metric(ix,p):
                n=int(y[ix].sum());m=len(ix)-n
                if not n or not m:return None
                return float((rankdata(p[ix])[y[ix]==1].sum()-n*(n+1)/2)/(n*m))
            grouping='requester_username clusters'
        else:
            groups=[np.array([i]) for i in range(len(labels))]
            def metric(ix,p):return float(np.log(np.maximum(p[ix],1e-15)).mean())
            grouping='rows; no source-document clusters available'
        draws=[np.concatenate([groups[j] for j in rng.integers(0,len(groups),len(groups))]) for _ in range(2000)]
        for b,a in CONTRASTS:
            seeds=[s for s in runner.SEEDS if (s,a) in prediction and (s,b) in prediction]
            if not seeds:continue
            def effect(ix):
                vals=[]
                for s in seeds:
                    va,vb=metric(ix,prediction[(s,a)]),metric(ix,prediction[(s,b)])
                    if va is None or vb is None:return None
                    vals.append(vb-va)
                return float(np.mean(vals))
            values=[effect(ix) for ix in draws];values=[v for v in values if v is not None]
            result.append(dict(task=task,contrast=b+'_minus_'+a,paired_seeds=seeds,
                observed_seed_mean=effect(np.arange(len(labels))),conditional_percentile_95=np.quantile(values,[.025,.975]).tolist(),
                requested_replicates=2000,valid_replicates=len(values),seed=116399,rows=len(labels),clusters=len(groups),grouping=grouping,
                limitation='Posthoc conditional interval on fixed trained models/reused development observations; no correction for prior research selection, across-task variation or training uncertainty.'))
    return result


def main():
    configure();plan=runner.check();job=read(R/'launch.json')['job']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip()
    account=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines()
    assert len(account)==1
    jid,state,elapsed,tres,exitcode,*_=account[0].split('|')
    assert jid==job and 'gres/gpu=1' in tres and state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'))
    out=R/'readout-v1';out.mkdir(mode=0o700,exist_ok=False)
    write(out/'analysis-plan.json',dict(plan_sha256=sha(R/'plan.json'),analysis_sha256=sha(__file__),
        contrasts=[b+'_minus_'+a for b,a in CONTRASTS],bootstrap_replicates=2000,bootstrap_seed=116399,
        purpose='posthoc control-capacity confound check, not a new method or old gate rescue'))
    freeze={str(p.relative_to(R)):sha(p) for p in R.glob('episode-*/action-0/*') if p.is_file() and p.name in ('receipt.json','submission.csv','progress.json')}
    write(out/'prediction-freeze.json',freeze)
    rows=[];errors=[];receipts={}
    for s in schedule():
        i=s['index'];ep=R/f'episode-{i}';act=ep/'action-0'
        done=read(ep/'completed.json') if (ep/'completed.json').exists() else {}
        row=dict(**s,completed=bool(done),valid=False,dev_metric=None,metric='auc' if s['task']==runner.TASKS[0] else 'log_loss',
            selected_C=None,selected_ngram=None,selected_min_df=None,selected_inner=None,all_grid_converged=None,final_converged=None,
            grid_fits=None,binary_fits=None,seconds=done.get('seconds'),prediction_sha256=None,inner_split_sha256=None,
            feature_count=None,source_commit=plan['source_commit'],error_type=done.get('error_type'),versions=None)
        if done.get('valid') and (ep/'closed.json').exists() and read(ep/'closed.json')['returncode']==0:
            rec=read(act/'receipt.json');receipts[i]=rec
            assert rec['grid_complete'] and rec['grid']==plan['grid'] and len(rec['rows'])==28
            assert rec['task']==s['task'] and rec['arm']==s['arm'] and rec['seed']==s['seed']
            assert [x['params'] for x in rec['rows']]==plan['grid']
            chosen=max(rec['rows'],key=lambda x:x['inner_oriented_score']);assert chosen==rec['selected']
            assert rec['classifier_fits']==29 and rec['features']<=(25000 if s['arm']=='word_25k' else 50000)
            assert rec['submission_sha256']==sha(act/'submission.csv')
            cfg=read(R/'configs'/f'{i}.json');scorer=Path(cfg['task']['search_only_dev_scorer_path'])
            assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
            mod=runner.load('capacity_scorer',scorer);v=mod.score(s['task'],act/'submission.csv')[row['metric']]
            v2=independent(s['task'],act/'submission.csv',mod.SPEC[s['task']]);err=abs(v-v2);assert err<1e-12;errors.append(err)
            row.update(valid=True,dev_metric=v,selected_C=chosen['params']['C'],selected_ngram=chosen['params']['ngram'],selected_min_df=chosen['params']['min_df'],
                selected_inner=chosen['inner_oriented_score'],all_grid_converged=all(x['converged'] for x in rec['rows']),final_converged=rec['final_converged'],
                grid_fits=28,binary_fits=rec['binary_fits'],prediction_sha256=rec['submission_sha256'],inner_split_sha256=rec['inner_split_sha256'],
                feature_count=rec['features'],versions=json.dumps(rec['versions'],sort_keys=True))
        rows.append(row)
    contrasts=paired(rows);per_task=[];inner=[]
    for task in runner.TASKS:
        for b,a in CONTRASTS:
            name=b+'_minus_'+a;vals=[r['difference'] for r in contrasts if r['task']==task and r['contrast']==name and r['complete']]
            per_task.append(dict(task=task,contrast=name,n=len(vals),median=statistics.median(vals) if vals else None,sample_variance=statistics.variance(vals) if len(vals)>1 else None))
        for seed in runner.SEEDS:
            group={r['arm']:r for r in rows if r['task']==task and r['seed']==seed}
            for b,a in CONTRASTS:
                if not (group[a]['valid'] and group[b]['valid']):continue
                aa,bb=receipts[group[a]['index']],receipts[group[b]['index']]
                diffs=[y['inner_oriented_score']-x['inner_oriented_score'] for x,y in zip(aa['rows'],bb['rows'])]
                inner.append(dict(task=task,seed=seed,contrast=b+'_minus_'+a,matched_grid_wins=sum(v>0 for v in diffs),configurations=28,
                    median_difference=statistics.median(diffs),gain_at_reference_selected_parameters=diffs[aa['selected']['grid_index']]))
    intervals=conditional_intervals(rows)
    # Already-public old control artifacts; this is replay identity, not a new seed.
    old_csv=PREV/'readout-v1/runs.csv'
    assert sha(old_csv)=='b0261bf57940227a9c74d894b87be658ee9d254f992374d7176db73ea6a80582'
    with old_csv.open(newline='') as f:previous=list(csv.DictReader(f))
    replay=[]
    for row in rows:
        if row['arm']=='word_25k':continue
        old=next(x for x in previous if x['task']==row['task'] and int(x['seed'])==row['seed'] and x['arm']==row['arm'])
        valid=row['valid'] and old['valid']=='True'
        replay.append(dict(task=row['task'],seed=row['seed'],arm=row['arm'],complete=valid,
            same_prediction_bytes=(row['prediction_sha256']==old['prediction_sha256']) if valid else None,
            same_inner_split=(row['inner_split_sha256']==old['inner_split_sha256']) if valid else None,
            same_versions=(row['versions']==old['versions']) if valid else None,
            score_difference=row['dev_metric']-float(old['dev_metric']) if valid else None))
    for rel,h in freeze.items():assert sha(R/rel)==h
    result=dict(protocol=plan['protocol'],job=job,source_commit=plan['source_commit'],plan_sha256=sha(R/'plan.json'),analysis_sha256=sha(__file__),
        assigned=12,complete=sum(r['valid'] for r in rows),allocation_state=state,allocation_seconds=int(elapsed),allocated_gpu_hours=int(elapsed)/3600,
        classifier_fits_completed=sum(29 for r in rows if r['valid']),binary_fits_completed=sum(r['binary_fits'] or 0 for r in rows),
        independent_scores=len(errors),max_absolute_verifier_error=max(errors,default=None),
        all_valid_fits_converged=all(r['all_grid_converged'] and r['final_converged'] for r in rows if r['valid']),
        contrasts=contrasts,per_task=per_task,
        matched_grid_diagnostics=inner,conditional_intervals=intervals,old_control_replay=replay,
        automatic_expansion=False,new_method_confirmed=False,old_gates_unchanged=True,
        limitations=plan['limitations'])
    write(out/'summary.json',result)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(out/'inner-grid.json',{str(i):dict(task=x['task'],arm=x['arm'],seed=x['seed'],rows=x['rows'],selected=x['selected'],versions=x['versions']) for i,x in receipts.items()})
    write(out/'export-receipt.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(result))


if __name__=='__main__':main()
