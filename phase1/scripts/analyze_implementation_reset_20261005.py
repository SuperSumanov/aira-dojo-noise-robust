"""Pre-result frozen full-denominator readout; labels stay in approved dev scorer.

No peeking until allocation closes. No changing missing runs to measured zeros.
"""
import csv, hashlib, importlib.util, json, math, os, statistics, subprocess
from pathlib import Path
from implementation_reset_20261005 import R, B, TASKS, read, write, sha, check, schedule

def summary(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
                sample_variance=statistics.variance(values) if len(values)>1 else None)

def independent(task, prediction, spec):
    import numpy as np
    from sklearn.metrics import roc_auc_score
    manifest=B/spec['view']/'manifest.json'
    assert sha(manifest)==spec['view_sha']
    labels_path=B/spec['source']/'private/dsearch.csv'
    assert sha(labels_path)==read(manifest)['source_dsearch_sha256']
    with labels_path.open(encoding='utf-8-sig',newline='') as f:labels=list(csv.DictReader(f))
    with prediction.open(encoding='utf-8-sig',newline='') as f:preds=list(csv.DictReader(f))
    keyed={r[spec['id']]:r for r in preds}
    assert len(keyed)==len(preds)==len(labels) and set(keyed)=={r[spec['id']] for r in labels}
    if task==TASKS[0]:
        return float(roc_auc_score([int(r[spec['label']]) for r in labels],[float(keyed[r[spec['id']]][spec['label']]) for r in labels]))
    p=np.array([[float(keyed[r['id']][c]) for c in ('EAP','HPL','MWS')] for r in labels])
    y=np.array([('EAP','HPL','MWS').index(r['author']) for r in labels]);assert np.isfinite(p).all()
    return float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean())

def oriented(a,b,task):return b-a if task==TASKS[1] else a-b

def main():
    plan=check();job=read(R/'launch.json')['job'];env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip(), 'batch still running'
    account=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines()
    assert len(account)==1
    jid,state,elapsed,tres,exitcode,*_=account[0].split('|')
    assert jid==job and state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY')) and 'gres/gpu=4' in tres
    out=R/'readout-v1';assert not out.exists();out.mkdir()
    scores={};checked=[];rows=[]
    for s in schedule():
        ep=R/f"episode-{s['index']}";cfg=read(R/'configs'/f"{s['index']}.json")
        scorer=Path(cfg['task']['search_only_dev_scorer_path']);assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
        module_spec=importlib.util.spec_from_file_location('reset_dev_scorer',scorer);m=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(m)
        metric_name='auc' if s['task']==TASKS[0] else 'log_loss'
        results=[]
        for ap in sorted(ep.glob('action-*'),key=lambda p:int(p.name.split('-')[1])):
            rp=ap/'result.json';sp=ap/'score.private.json'
            if sp.exists():
                rec=read(sp);prediction=ap/'submission.private.csv';assert sha(prediction)==rec['receipt']['submission_sha256']
                value=independent(s['task'],prediction,m.SPEC[s['task']]);err=abs(value-rec['receipt'][metric_name]);assert err<=1e-12
                checked.append(dict(index=s['index'],action=ap.name,absolute_error=err,timely=rec['elapsed_seconds']<=600))
                scores[(s['index'],ap.name)]=value
            if rp.exists():
                r=read(rp);assert r['elapsed_seconds']<=600
                if r['valid']:assert abs(r['metric']-scores[(s['index'],ap.name)])<=1e-12
                results.append((ap.name,r))
        incumbent=None;root=R/f"episode-{s['start']}"/'first-valid.private.json'
        if root.exists():
            first=read(root);assert abs(first['metric']-scores[(s['start'],'action-'+str(first['step']))])<=1e-12
            incumbent=first['metric']
        attempted=(ep/'launch.json').exists();finished=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        candidates=[(a,r) for a,r in results if r['valid']]
        selected=incumbent;selected_action='incumbent' if incumbent is not None else None
        for a,r in candidates:
            if selected is None or oriented(r['metric'],selected,s['task'])>0:selected=r['metric'];selected_action=a
        if not attempted:selected=None;selected_action=None
        row=dict(**s,attempted=attempted,worker_status=finished.get('status','not_started' if not attempted else 'missing_finished'),
            source_metric=incumbent,final_dev_metric=selected,selected_action=selected_action,
            improvement=None if selected is None or incumbent is None else oriented(selected,incumbent,s['task']),
            valid_new=len(candidates),executed=len(results),generated=len(list(ep.glob('action-*/generation.private.json'))),
            closed=(ep/'closed.json').exists(),run_budget_seconds=600,source_commit=plan['source_commit'])
        rows.append(row)
    contrasts=[]
    for start in range(4):
        group={r['arm']:r for r in rows if r['arm']!='ROOT' and r['start']==start}
        assert len(group)==3
        task=group['continue']['task'];pair=dict(start=start,task=task)
        complete=all(r['closed'] and r['worker_status'] in ('completed','budget_exhausted') and r['final_dev_metric'] is not None for r in group.values())
        pair['complete']=complete
        for control in ('continue','new_idea'):
            pair['reimplement_minus_'+control]=oriented(group['reimplement']['final_dev_metric'],group[control]['final_dev_metric'],task) if complete else None
        contrasts.append(pair)
    per_task=[]
    for task in TASKS:
        pairs=[p for p in contrasts if p['task']==task]
        per_task.append(dict(task=task,complete_pairs=sum(p['complete'] for p in pairs),
            contrasts={c:summary([p['reimplement_minus_'+c] for p in pairs if p['complete']]) for c in ('continue','new_idea')}))
    gate=read(R/'source-gate.json') if (R/'source-gate.json').exists() else {'passed':False,'reason':'not_reached'}
    report=dict(status='CLOSED_EXPLORATORY_QUALIFICATION',job=job,allocation_state=state,exit_code=exitcode,
        allocation_seconds=int(elapsed),allocated_gpu_hours=4*int(elapsed)/3600,plan_sha256=sha(R/'plan.json'),
        roots_assigned=4,continuations_assigned=12,roots_valid=sum(r['arm']=='ROOT' and r['valid_new']>0 for r in rows),
        continuations_attempted=sum(r['arm']!='ROOT' and r['attempted'] for r in rows),source_gate=gate,
        independent_scores=len(checked),max_independent_abs_error=max((x['absolute_error'] for x in checked),default=None),
        contrasts=contrasts,per_task=per_task,
        numerical_signal=all(p['complete'] and p['reimplement_minus_continue']>0 and p['reimplement_minus_new_idea']>0 for p in contrasts),
        semantic_review_complete=False,automatic_expansion=False,
        limitation='Four paired starts on two reused dev tasks, broad pre-specified TFIDF/LR idea. Implementation reset is bundled with context removal and native operator routing. Neither learned selector, algorithm novelty, nor independent full-search gain confirmed.')
    write(out/'summary.json',report);write(out/'independent-checks.json',checked)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(out/'export-receipt.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
