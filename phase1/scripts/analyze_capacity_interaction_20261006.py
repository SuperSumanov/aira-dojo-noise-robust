"""Missing-cell mechanism readout; reused development task, not a method claim."""
import csv
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

from capacity_interaction_20261006 import R, B, DONOR, TASK, configure, runner, schedule, read, write, sha
from analyze_matched_representation_20261005 import independent

PLAN='5f30bc3dbaa840475d8f473c4e56566afe0bd5d408268adf7d784679f5f1b359'
OLD_CSV='6ad57a3afeb04d36dba603eb045300441295c600faf3cd2b1e42b00bc793be8d'
OLD_SUMMARY='d0166d17b774b4e2b48cfe105477e0c796c15faa7e2de10c0cae7e0ac032315b'


def effect(w25, w50, low, full):
    """All inputs are log losses; positive outputs mean a loss reduction."""
    if low is None or full is None:
        return dict(full_minus_reduced_union=None, interaction=None, full_union_minus_word50=None)
    return dict(full_minus_reduced_union=low-full,
                interaction=(low-full)-(w25-w50), full_union_minus_word50=w50-full)


def paired(rows, old):
    ans=[]
    for seed in runner.SEEDS:
        pair={x['arm']:x for x in rows if x['seed']==seed}
        assert set(pair)=={'word_char','word50_char'}
        base={x['arm']:x for x in old if x['task']==TASK and int(x['seed'])==seed}
        assert all(base[a]['valid']=='True' for a in ('word','word_25k','word_char'))
        valid=all(x['valid'] for x in pair.values())
        if valid:
            for field in ('inner_split_sha256','versions'):
                assert len({pair[a][field] for a in pair}|{base[a][field] for a in base})==1,field
        ans.append(dict(seed=seed,complete=valid,**effect(float(base['word_25k']['dev_metric']),float(base['word']['dev_metric']),
            pair['word_char']['dev_metric'] if valid else None,pair['word50_char']['dev_metric'] if valid else None)))
    return ans


def conditional_intervals(rows,old):
    import numpy as np
    cfg=read(R/'configs/0.json');scorer=Path(cfg['task']['search_only_dev_scorer_path'])
    assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
    spec=runner.load('interaction_boot_scorer',scorer).SPEC[TASK]
    manifest=B/spec['view']/'manifest.json';assert sha(manifest)==spec['view_sha']
    labels=B/spec['source']/'private/dsearch.csv';assert sha(labels)==read(manifest)['source_dsearch_sha256']
    with labels.open(newline='',encoding='utf-8-sig') as f:truth=list(csv.DictReader(f))
    ids={r['id'] for r in truth};assert len(ids)==len(truth)
    def losses(root,row):
        path=root/f"episode-{row['index']}"/'action-0/submission.csv';assert sha(path)==row['prediction_sha256']
        with path.open(newline='',encoding='utf-8-sig') as f:pp=list(csv.DictReader(f))
        p={r['id']:r for r in pp};assert len(p)==len(pp)==len(truth) and set(p)==ids
        v=np.asarray([float(p[r['id']][r['author']]) for r in truth]);assert np.isfinite(v).all() and ((v>=0)&(v<=1)).all()
        return -np.log(np.maximum(v,1e-15))
    cells=[];seeds=[]
    for seed in runner.SEEDS:
        rr={r['arm']:r for r in rows if r['seed']==seed}
        if not all(r['valid'] for r in rr.values()):continue
        oo={r['arm']:r for r in old if r['task']==TASK and int(r['seed'])==seed}
        cells.append(effect(losses(DONOR,oo['word_25k']),losses(DONOR,oo['word']),losses(R,rr['word_char']),losses(R,rr['word50_char'])))
        seeds.append(seed)
    if not cells:return []
    # Identical observation indices across all four cells and both fitted splits.
    rng=np.random.default_rng(116499)
    vectors={key:np.mean([x[key] for x in cells],axis=0) for key in cells[0]}
    boots={key:[] for key in vectors}
    for _ in range(2000):
        ix=rng.integers(0,len(truth),len(truth))
        for key,v in vectors.items():boots[key].append(float(v[ix].mean()))
    return [dict(contrast=k,paired_seeds=seeds,observed_seed_mean=float(v.mean()),
        conditional_percentile_95=np.quantile(boots[k],[.025,.975]).tolist(),rows=len(truth),replicates=2000,seed=116499,
        limitation='Posthoc conditional row bootstrap, fixed models and reused dev data; no document clusters or development-selection/training/task correction.') for k,v in vectors.items()]


def main():
    configure();assert sha(R/'plan.json')==PLAN;plan=runner.check()
    assert sha(DONOR/'readout-v1/runs.csv')==OLD_CSV and sha(DONOR/'readout-v1/summary.json')==OLD_SUMMARY
    with (DONOR/'readout-v1/runs.csv').open(newline='') as f:old=list(csv.DictReader(f))
    job=read(R/'launch.json')['job'];env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip()
    account=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines()
    assert len(account)==1
    jid,state,elapsed,tres,exitcode,*_=account[0].split('|')
    assert jid==job and 'gres/gpu=1' in tres and state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'))
    out=R/'readout-v1';out.mkdir(mode=0o700,exist_ok=False)
    write(out/'analysis-plan.json',dict(plan_sha256=PLAN,analysis_sha256=sha(__file__),donor_csv_sha256=OLD_CSV,donor_summary_sha256=OLD_SUMMARY,
        primary='full_minus_reduced_union',secondary=['interaction','full_union_minus_word50'],bootstrap_seed=116499,
        interpretation='Four-cell interaction test of a known representation, not equal-feature-budget or autonomous method comparison.'))
    freeze={str(p.relative_to(R)):sha(p) for p in R.glob('episode-*/action-0/*') if p.is_file() and p.name in ('receipt.json','submission.csv','progress.json')}
    write(out/'prediction-freeze.json',freeze)
    rows=[];errors=[];receipts={}
    for s in schedule():
        i=s['index'];ep=R/f'episode-{i}';act=ep/'action-0';done=read(ep/'completed.json') if (ep/'completed.json').exists() else {}
        row=dict(**s,completed=bool(done),valid=False,dev_metric=None,metric='log_loss',
            selected_C=None,selected_ngram=None,selected_min_df=None,selected_inner=None,all_grid_converged=None,final_converged=None,
            seconds=done.get('seconds'),program_seconds=None,prediction_sha256=None,inner_split_sha256=None,
            feature_count=None,classifier_fits=None,binary_fits=None,source_commit=plan['source_commit'],versions=None,error_type=done.get('error_type'))
        if done.get('valid') and (ep/'closed.json').exists() and read(ep/'closed.json')['returncode']==0:
            rec=read(act/'receipt.json');receipts[i]=rec
            assert rec['task']==TASK and rec['arm']==s['arm'] and rec['seed']==s['seed']
            assert rec['grid_complete'] and rec['grid']==plan['grid'] and len(rec['rows'])==28 and rec['classifier_fits']==29
            assert [x['params'] for x in rec['rows']]==plan['grid']
            chosen=max(rec['rows'],key=lambda x:x['inner_oriented_score']);assert chosen==rec['selected']
            assert rec['features']<=(75000 if s['arm']=='word50_char' else 50000)
            assert rec['submission_sha256']==sha(act/'submission.csv')
            cfg=read(R/'configs'/f'{i}.json');scorer=Path(cfg['task']['search_only_dev_scorer_path'])
            old_row=next(x for x in old if x['task']==TASK and int(x['seed'])==s['seed'] and x['arm']=='word_char')
            old_cfg=read(DONOR/'configs'/f"{old_row['index']}.json")
            for key in ('data_dir','public_dir','search_only_dev_scorer_path','search_only_dev_scorer_sha256'):
                assert cfg['task'][key]==old_cfg['task'][key]
            assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
            m=runner.load('interaction_scorer',scorer);value=m.score(TASK,act/'submission.csv')['log_loss']
            other=independent(TASK,act/'submission.csv',m.SPEC[TASK]);err=abs(value-other);assert err<1e-12;errors.append(err)
            row.update(valid=True,dev_metric=value,selected_C=chosen['params']['C'],selected_ngram=chosen['params']['ngram'],
                selected_min_df=chosen['params']['min_df'],selected_inner=chosen['inner_oriented_score'],all_grid_converged=all(x['converged'] for x in rec['rows']),
                final_converged=rec['final_converged'],program_seconds=rec['elapsed_seconds'],prediction_sha256=rec['submission_sha256'],
                inner_split_sha256=rec['inner_split_sha256'],feature_count=rec['features'],classifier_fits=rec['classifier_fits'],binary_fits=rec['binary_fits'],versions=json.dumps(rec['versions'],sort_keys=True))
        rows.append(row)
    contrasts=paired(rows,old);per_contrast=[];inner=[];replay=[]
    for key in ('full_minus_reduced_union','interaction','full_union_minus_word50'):
        values=[r[key] for r in contrasts if r['complete']]
        per_contrast.append(dict(contrast=key,n=len(values),median=statistics.median(values) if values else None,sample_variance=statistics.variance(values) if len(values)>1 else None))
    for seed in runner.SEEDS:
        pp={r['arm']:r for r in rows if r['seed']==seed}
        if all(r['valid'] for r in pp.values()):
            a,b=[receipts[pp[k]['index']] for k in ('word_char','word50_char')]
            ds=[y['inner_oriented_score']-x['inner_oriented_score'] for x,y in zip(a['rows'],b['rows'])]
            inner.append(dict(seed=seed,matched_grid_wins=sum(v>0 for v in ds),configurations=28,median_gain=statistics.median(ds),gain_at_reduced_selected_params=ds[a['selected']['grid_index']]))
        rr=pp['word_char'];oo=next(x for x in old if x['task']==TASK and int(x['seed'])==seed and x['arm']=='word_char')
        replay.append(dict(seed=seed,complete=rr['valid'],same_prediction_bytes=rr['prediction_sha256']==oo['prediction_sha256'] if rr['valid'] else None,
            metric_difference=rr['dev_metric']-float(oo['dev_metric']) if rr['valid'] else None))
    intervals=conditional_intervals(rows,old)
    for rel,h in freeze.items():assert sha(R/rel)==h
    summary=dict(job=job,protocol=plan['protocol'],source_commit=plan['source_commit'],plan_sha256=PLAN,analysis_sha256=sha(__file__),
        allocation_state=state,exit_code=exitcode,allocation_seconds=int(elapsed),allocated_gpu_hours=int(elapsed)/3600,
        assigned=4,valid=sum(r['valid'] for r in rows),independent_scores=len(errors),max_absolute_verifier_error=max(errors,default=None),
        classifier_fits_completed=sum(r['classifier_fits'] or 0 for r in rows),binary_fits_completed=sum(r['binary_fits'] or 0 for r in rows),
        all_valid_fits_converged=all(r['all_grid_converged'] and r['final_converged'] for r in rows if r['valid']),
        contrasts=contrasts,per_contrast=per_contrast,conditional_intervals=intervals,matched_grid_diagnostics=inner,old_union_replay=replay,
        new_method_confirmed=False,automatic_expansion=False,not_equal_feature_budget=True,limitations=plan['limitations'])
    write(out/'summary.json',summary)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(out/'inner-grid.json',{str(i):dict(task=r['task'],seed=r['seed'],arm=r['arm'],rows=r['rows'],selected=r['selected']) for i,r in receipts.items()})
    write(out/'export-receipt.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(summary))


def tests():
    x=effect(.6,.5,.4,.35);assert abs(x['full_minus_reduced_union']-.05)<1e-12 and abs(x['interaction']+.05)<1e-12
    assert all(v is None for v in effect(.6,.5,None,.35).values())
    rows=[];old=[]
    for seed in runner.SEEDS:
        for arm,value in [('word',.5),('word_25k',.6),('word_char',.4)]:old.append(dict(task=TASK,seed=seed,arm=arm,valid='True',dev_metric=value,inner_split_sha256='same',versions='same'))
        for arm,value in [('word_char',.4),('word50_char',.35)]:rows.append(dict(seed=seed,arm=arm,valid=True,dev_metric=value,inner_split_sha256='same',versions='same'))
    assert len(paired(rows,old))==2
    rows[0]['valid']=False;assert paired(rows,old)[0]['full_minus_reduced_union'] is None
    rows[0]['valid']=True;rows[0]['inner_split_sha256']='different'
    try:paired(rows,old)
    except AssertionError:pass
    else:raise AssertionError('split mismatch not rejected')
    print('INTERACTION_ANALYSIS_TESTS_PASS orientation_missing_split')


if __name__=='__main__':
    if '--tests' in sys.argv:tests()
    else:main()
