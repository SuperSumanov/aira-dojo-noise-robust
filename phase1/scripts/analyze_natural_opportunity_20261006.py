"""Closed-batch, conditional opportunity readout; never source-outcome selection."""
import csv
import json
import math
import os
import re
import statistics
import subprocess
import time

from natural_opportunity_20261006 import B,R,TASKS,check,load,read,schedule,sha,write


def oriented(task,p,c):
    assert task in TASKS
    if p is None or c is None:return None
    assert math.isfinite(p) and math.isfinite(c)
    return (c-p)*(1 if task==TASKS[0] else -1)


def aggregate(task,rows,threshold,ratio_cap):
    pairs=[]
    for repeat in range(2):
        q={r['arm']:r for r in rows if r['repeat']==repeat}
        assert set(q)=={'P','C'}
        p,c=q['P'],q['C'];valid=p['valid'] and c['valid']
        pairs.append(dict(repeat=repeat,complete=valid,
            gain=oriented(task,p['dev_metric'],c['dev_metric']) if valid else None,
            P=p['dev_metric'],C=c['dev_metric'],parent_worker_seconds=p['seconds'],child_worker_seconds=c['seconds'],
            cost_ratio=c['seconds']/p['seconds'] if valid and p['seconds']>0 else None,
            same_prediction=p['prediction_sha256']==c['prediction_sha256'] if valid else None))
    complete=all(x['complete'] for x in pairs)
    vals=[x['gain'] for x in pairs if x['complete']]
    ratios=[x['cost_ratio'] for x in pairs if x['cost_ratio'] is not None]
    median_ratio=statistics.median(ratios) if len(ratios)==2 else None
    return dict(task=task,pairs=pairs,complete=complete,
        median_gain=statistics.median(vals) if vals else None,
        restart_gain_sample_variance=statistics.variance(vals) if len(vals)==2 else None,
        median_worker_time_ratio=median_ratio,
        both_restarts_meaningful=complete and all(x>=threshold for x in vals),
        cost_gate=median_ratio is not None and median_ratio<=ratio_cap,
        pareto_point_estimate=complete and all(x>0 for x in vals) and median_ratio is not None and median_ratio<=1,
        restart_prediction_identical={arm:len({r['prediction_sha256'] for r in rows if r['arm']==arm and r['valid']})==1
            if sum(r['valid'] for r in rows if r['arm']==arm)==2 else None for arm in ['P','C']})


def tests():
    assert oriented(TASKS[0],.5,.75)==.25 and oriented(TASKS[1],.75,.5)==.25
    assert oriented(TASKS[0],None,.8) is None
    rows=[dict(repeat=k,arm=a,valid=True,dev_metric=.5 if a=='P' else .6,
        seconds=10 if a=='P' else 12,prediction_sha256=a) for k in range(2) for a in ['P','C']]
    x=aggregate(TASKS[0],rows,.005,1.5)
    assert x['both_restarts_meaningful'] and x['cost_gate'] and not x['pareto_point_estimate']
    rows[0]['valid']=False
    assert not aggregate(TASKS[0],rows,.005,1.5)['both_restarts_meaningful']
    return dict(status='PASS',orientation=True,missing_not_imputed=True,restarts_not_independent_parents=True)


def aligned(task,path,spec):
    import numpy as np
    manifest=B/spec['view']/'manifest.json';assert sha(manifest)==spec['view_sha']
    labels=B/spec['source']/'private/dsearch.csv'
    assert sha(labels)==read(manifest)['source_dsearch_sha256']
    with labels.open(newline='',encoding='utf-8-sig') as f:truth=list(csv.DictReader(f))
    with path.open(newline='',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
    q={r[spec['id']]:r for r in rows}
    assert len(q)==len(rows)==len(truth) and set(q)=={r[spec['id']] for r in truth}
    if task==TASKS[0]:
        y=np.array([int(r[spec['label']]) for r in truth])
        p=np.array([float(q[r[spec['id']]][spec['label']]) for r in truth])
    else:
        y=np.array([r['author'] for r in truth])
        p=np.array([float(q[r['id']][r['author']]) for r in truth])
    assert np.isfinite(p).all()
    return y,p


def independent(task,y,p):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y,p)) if task==TASKS[0] else float(-np.log(np.maximum(p,1e-15)).mean())


def interval(task,arrays):
    import numpy as np
    # Identical resampled evaluation examples for P/C and both restarts.
    y=arrays[(0,'P')][0]
    assert all(np.array_equal(y,v[0]) for v in arrays.values())
    rng=np.random.default_rng(117699)
    groups=[np.flatnonzero(y==v) for v in np.unique(y)]
    draws=[]
    for _ in range(4000):
        ix=np.concatenate([rng.choice(g,len(g),replace=True) for g in groups]) if task==TASKS[0] else rng.integers(0,len(y),len(y))
        gains=[oriented(task,independent(task,y[ix],arrays[(k,'P')][1][ix]),
            independent(task,y[ix],arrays[(k,'C')][1][ix])) for k in range(2)]
        draws.append(statistics.median(gains))
    lo,hi=np.quantile(draws,[.00625,.99375])
    return dict(n=len(y),replicates=4000,seed=117699,confidence=.9875,
        low=float(lo),high=float(hi),conditional=True,
        caveat='Evaluation-example uncertainty only, not training-source/seed/generalization uncertainty or historical selection correction')


def main():
    started=time.monotonic();plan=check();job=read(R/'launch.json')['job']
    assert read(R/'closed.json')['assigned']==16
    assert all((R/f'episode-{i}/closed.json').exists() for i in range(16))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip()
    account=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines()
    assert len(account)==1
    jid,state,elapsed,tres,exitcode,*_=account[0].split('|')
    assert jid==job and re.search(r'(?:^|,)gres/gpu=1(?:,|$)',tres)
    assert state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY'))
    out=R/'readout-v1';out.mkdir(mode=0o700,exist_ok=False)
    freeze={str(p.relative_to(R)):sha(p) for p in R.glob('episode-*/action-0/submission.private.csv')}
    write(out/'prediction-freeze.json',freeze)
    rows=[];verified=[];arrays={};failures=[]
    for s in schedule():
        ep=R/f"episode-{s['index']}";pred=ep/'action-0/submission.private.csv'
        done=read(ep/'completed.json') if (ep/'completed.json').exists() else {}
        closure=read(ep/'closed.json')
        row=dict(**s,completed=bool(done),valid=False,dev_metric=None,
            metric='auc' if s['task']==TASKS[0] else 'log_loss',seconds=done.get('seconds'),
            exec_seconds=done.get('exec_seconds'),timed_out=done.get('timed_out'),
            error_type=done.get('error_type') or closure.get('reason'),step_returncode=closure['returncode'],
            started=(ep/'native.json').exists(),integrity_eligible=s['case'] not in plan['pre_execution_excluded_cases'],
            prediction_sha256=None,source_commit=plan['source_commit'])
        if done.get('valid_execution') and row['step_returncode']==0:
            assert sha(pred)==done['prediction_sha256']
            cfg=read(R/'configs'/f"{s['index']}.json")['task']
            assert sha(cfg['search_only_dev_scorer_path'])==cfg['search_only_dev_scorer_sha256']
            m=load('natural_opportunity_scorer',cfg['search_only_dev_scorer_path'])
            try:result=m.score(s['task'],pred)
            except m.InvalidSubmissionError:row['error_type']='InvalidSubmissionError'
            else:
                y,p=aligned(s['task'],pred,m.SPEC[s['task']]);v=result[row['metric']]
                v2=independent(s['task'],y,p);assert math.isfinite(v) and abs(v-v2)<1e-12
                verified.append(abs(v-v2));arrays[(s['case'],s['repeat'],s['arm'])]=(y,p)
                row.update(valid=True,dev_metric=v,prediction_sha256=sha(pred))
        if not row['valid']:
            terminal_path=ep/'action-0/terminal.private.json'
            terminal=read(terminal_path)['terminal'] if terminal_path.exists() else ''
            failures.append(dict(index=s['index'],case=s['case'],repeat=s['repeat'],arm=s['arm'],
                terminal_sha256=sha(terminal_path) if terminal_path.exists() else None,
                exception_classes=sorted(set(re.findall(r'(?m)^([A-Za-z_][A-Za-z_0-9]*(?:Error|Exception)):',terminal))),
                error_type=row['error_type'],timed_out=row['timed_out'],no_repair=True))
        rows.append(row)
    parents=[]
    for case in range(4):
        rr=[r for r in rows if r['case']==case];assert len(rr)==4
        task=rr[0]['task'];q=aggregate(task,rr,plan['meaningful_gain'][task],plan['time_ratio_ceiling'])
        q['case']=case
        q['interval']=interval(task,{(k,a):arrays[(case,k,a)] for k in range(2) for a in ['P','C']}) if q['complete'] else None
        q['screen_pass']=q['both_restarts_meaningful'] and q['cost_gate'] and q['interval']['low']>0
        parents.append(q)
    tasks=[]
    for task in TASKS:
        rr=[p for p in parents if p['task']==task];g=[p['median_gain'] for p in rr if p['complete']]
        tasks.append(dict(task=task,assigned_parents=len(rr),complete_parents=sum(p['complete'] for p in rr),
            median_parent_gain=statistics.median(g) if g else None,
            descriptive_parent_sample_variance=statistics.variance(g) if len(g)>1 else None,
            qualifying_parents=sum(p['screen_pass'] for p in rr)))
    for rel,h in freeze.items():assert sha(R/rel)==h
    summary=dict(protocol=plan['protocol'],source_commit=plan['source_commit'],plan_sha256=sha(R/'plan.json'),
        analysis_sha256=sha(__file__),tests=tests(),job=job,state=state,exitcode=exitcode,
        assigned=16,started_programs=sum(r['started'] for r in rows),pre_excluded_programs=sum(not r['integrity_eligible'] for r in rows),
        valid_programs=sum(r['valid'] for r in rows),complete_parents=sum(p['complete'] for p in parents),
        parents=parents,per_task=tasks,failures=failures,independent_scores=len(verified),
        max_absolute_verifier_error=max(verified,default=None),allocation_seconds=int(elapsed),
        allocated_gpu_hours=int(elapsed)/3600,worker_seconds_total=sum(r['seconds'] or 0 for r in rows),
        program_seconds_total=sum(r['exec_seconds'] or 0 for r in rows),analysis_seconds=time.monotonic()-started,
        opportunity_screen_pass=all(t['qualifying_parents']>=1 for t in tasks),
        independent_run_confirmation=False,cross_training_seed_confirmation=False,
        new_method_confirmed=False,selector_trained=False,equal_full_cost_strong_baseline_tested=False,
        automatic_expansion=False,protected_opened=False,paid_api_calls=0,
        limitations=[plan['independence'],plan['seed_boundary'],plan['cost'],plan['uncertainty'],plan['amendment'],plan['exclusion_evidence']])
    write(out/'summary.json',summary)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(out/'export-receipt.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(summary))


if __name__=='__main__':
    import sys
    os.umask(0o077)
    if sys.argv[1:]==['--tests']:print(json.dumps(tests()))
    else:assert not sys.argv[1:];main()
