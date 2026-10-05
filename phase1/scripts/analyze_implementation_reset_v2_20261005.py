"""Closed-only full-denominator v2 readout. Independent development rescoring.

No outcome visibility during source selection/configuration; no post-hoc rescue.
"""
import csv, hashlib, importlib.util, json, os, statistics, subprocess
from implementation_reset_v2_20261005 import R, read, write, sha, check, schedule, contract
from analyze_implementation_reset_20261005 import independent, oriented, summary

def main():
    plan=check();job=read(R/'launch.json')['job']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    assert not subprocess.check_output(['squeue','-j',job,'-h','-o','%i'],env=env,text=True,timeout=20).strip()
    account=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=20).strip().splitlines()
    assert len(account)==1
    jid,state,elapsed,tres,exitcode,*_=account[0].split('|')
    assert jid==job and state.startswith(('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY')) and 'gres/gpu=4' in tres
    assert (R/'closed.json').exists() and read(R/'closed.json')['service_closed']
    out=R/'readout-v1';assert not out.exists();out.mkdir()
    rows=[];checked=[];source_scores={};semantics=[]
    for s in schedule():
        ep=R/f"episode-{s['index']}";cfg=read(R/'configs'/f"{s['index']}.json")
        scorer=cfg['task']['search_only_dev_scorer_path'];assert sha(scorer)==cfg['task']['search_only_dev_scorer_sha256']
        spec=importlib.util.spec_from_file_location('v2_frozen_scorer',scorer)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        metric='auc' if s['task']==contract.TASKS[0] else 'log_loss'
        results=[]
        for ap in sorted(ep.glob('action-*'),key=lambda p:int(p.name.split('-')[1])):
            sp=ap/'score.private.json';rp=ap/'result.json';ind=None
            if sp.exists():
                record=read(sp);prediction=ap/'submission.private.csv'
                assert sha(prediction)==record['receipt']['submission_sha256']
                ind=independent(s['task'],prediction,m.SPEC[s['task']])
                err=abs(ind-record['receipt'][metric]);assert err<=1e-12
                checked.append(dict(index=s['index'],action=ap.name,absolute_error=err,timely=record['elapsed_seconds']<=600))
            if rp.exists():
                result=read(rp);assert result['elapsed_seconds']<=600
                if result['valid']:
                    assert ind is not None and abs(result['metric']-ind)<=1e-12
                    code=read(ap/'code.private.json')['code']
                    assert hashlib.sha256(code.encode()).hexdigest()==result['code_sha256']
                results.append((ap.name,result))
        if s['arm']=='ROOT':
            p=ep/'first-valid.private.json'
            if p.exists():
                src=read(p);r=dict(results)['action-'+str(src['step'])]
                assert r['valid'] and src['code']==contract.source_program(s['task'],s['execution_seed']) and abs(src['metric']-r['metric'])<=1e-12
                source_scores[s['start']]=src['metric']
        source=source_scores.get(s['start']);selected=source;selected_action='incumbent' if source is not None else None
        valid=[(a,r) for a,r in results if r['valid']]
        for a,r in valid:
            if selected is None or oriented(r['metric'],selected,s['task'])>0:
                selected=r['metric'];selected_action=a
        attempted=(ep/'launch.json').exists();closed=(ep/'closed.json').exists()
        finished=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        if not attempted:selected=None;selected_action=None
        rows.append(dict(**s,attempted=attempted,closed=closed,worker_status=finished.get('status','missing_finished' if attempted else 'not_started'),
            source_metric=source,final_dev_metric=selected,selected_action=selected_action,
            improvement=None if source is None or selected is None else oriented(selected,source,s['task']),
            generated=len(list(ep.glob('action-*/generation.private.json'))),executed=len(results),valid_new=len(valid),
            contract_rejections=len(list(ep.glob('action-*/contract-rejection.json'))),
            generation_timeouts=len(list(ep.glob('action-*/generation-failure.json'))),
            budget_seconds=600,source_commit=plan['source_commit']))
        if selected_action not in (None,'incumbent') and s['arm'] not in ('ROOT','random_hpo'):
            semantics.append(dict(index=s['index'],selected_action=selected_action,review_complete=False,
                                  note='Selected syntax/family screen is not blinded semantic verification.'))
    contrasts=[]
    for task in contract.TASKS:
        subset=[r for r in rows if r['task']==task and r['arm']!='ROOT']
        for seed in sorted({r['seed'] for r in subset}):
            group={r['arm']:r for r in subset if r['seed']==seed};assert set(group)==set(contract.ARMS)
            complete=all(r['closed'] and r['worker_status'] in ('completed','budget_exhausted') and r['final_dev_metric'] is not None for r in group.values())
            pair=dict(task=task,seed=seed,complete=complete)
            for control in ('continue','new_idea','random_hpo'):
                pair['reimplement_minus_'+control]=oriented(group['reimplement']['final_dev_metric'],group[control]['final_dev_metric'],task) if complete else None
            contrasts.append(pair)
    per_task=[dict(task=task,contrasts={k:summary([p['reimplement_minus_'+k] for p in contrasts if p['task']==task and p['complete']]) for k in ('continue','new_idea','random_hpo')}) for task in contract.TASKS]
    report=dict(status='CLOSED_EXPLORATORY_FIXED_SOURCE_COMPARISON',job=job,allocation_state=state,exit_code=exitcode,
        allocation_seconds=int(elapsed),allocated_gpu_hours=4*int(elapsed)/3600,plan_sha256=sha(R/'plan.json'),
        independent_source_ideas=2,generation_seeds_per_task=2,comparison_assignments=16,
        fixed_sources_valid=len(source_scores),comparisons_attempted=sum(r['attempted'] and r['arm']!='ROOT' for r in rows),
        independent_scores=len(checked),max_independent_abs_error=max((r['absolute_error'] for r in checked),default=None),
        contrasts=contrasts,per_task=per_task,numerical_screen=contract.decision(contrasts),
        semantic_review_complete=False,automatic_expansion=False,
        limitation='Conditional two-task reused development comparison. Human fixed baseline, two generation seeds, context/operator bundled treatment; no learned selector or independent full-search benefit established.')
    write(out/'summary.json',report);write(out/'independent-checks.json',checked);write(out/'semantic-review-pending.json',semantics)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write(out/'export-receipt.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print(json.dumps(report))

if __name__=='__main__':main()
