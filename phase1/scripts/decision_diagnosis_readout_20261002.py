"""Pre-outcome readout: no partial-winner selection, all eight starts retained."""
import argparse, csv, hashlib, json, math, statistics, subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/decision-diagnosis-20261002-v1')
def read(p): return json.loads(p.read_bytes())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    with p.open('x') as f: json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False)
def status():
    p=read(R/'plan.json'); rows=[]
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}'
        rows.append(dict(index=s['index'],wave=s['wave'],arm=s['arm'],task=s['task'],
            launched=(ep/'launch.json').exists(),closed=(ep/'closed.json').exists(),
            generated=sum(1 for _ in ep.glob('action-*/generation.private.json')),
            returned=sum(1 for _ in ep.glob('action-*/result.json')),
            failure=(read(ep/'failure.json')['error_type'] if (ep/'failure.json').exists() else None)))
    return dict(job=read(R/'launch.json')['job'] if (R/'launch.json').exists() else None,
        claim=(R/'claim.json').exists(),ready=(R/'service-ready.json').exists(),
        all_closed=(R/'all-closed.json').exists(),allocation_closed=(R/'closed.json').exists(),
        controller_error=(read(R/'controller-error.json') if (R/'controller-error.json').exists() else None),
        rows=rows)
def analyze():
    if not (R/'all-closed.json').exists() or not (R/'closed.json').exists():
        raise ValueError('complete batch closure required, no partial efficacy readout')
    p=read(R/'plan.json'); rows=[]; actions=[]
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}'; closed=read(ep/'closed.json')
        lower=s['task']=='spooky-author-identification'
        seen=[]; costs=[]; modes=[]
        for step in range(3):
            a=ep/f'action-{step}'; path=a/'result.json'
            result=read(path) if path.exists() else None
            gen=read(a/'generation.private.json') if (a/'generation.private.json').exists() else None
            if gen: costs.append(gen['generation_seconds'])
            if result:
                assert result['elapsed_seconds']<=p['run_seconds']
                if result['valid']:
                    assert result['kind']=='SOLUTION' and math.isfinite(result['metric'])
                    seen.append((result['metric'],step))
                modes.append(result['kind'])
            actions.append(dict(index=s['index'],step=step,task=s['task'],arm=s['arm'],seed=s['seed'],
                generated=gen is not None,generation_seconds=gen['generation_seconds'] if gen else None,
                completion_tokens=(gen.get('usage',{}).get('completion_tokens') if gen else None),
                returned=result is not None,kind=result['kind'] if result else None,
                valid=result['valid'] if result else False,metric=result['metric'] if result else None,
                successful_check=result.get('successful_check',False) if result else False,
                exec_seconds=result['exec_seconds'] if result else None))
        init_path=ep/'action-0/result.json'; initial=read(init_path)['metric'] if init_path.exists() and read(init_path)['valid'] else None
        best=(min(seen) if lower else max(seen,key=lambda x:x[0])) if seen else (None,None)
        saved=[read(x)['selected_metric'] for x in sorted(ep.glob('action-*/result.json'))]
        if saved: assert saved[-1]==best[0]
        gain=(initial-best[0] if lower else best[0]-initial) if initial is not None and best[0] is not None else None
        rows.append(dict(**s,initial=initial,selected=best[0],selected_step=best[1],gain=gain,
            generation_seconds=sum(costs),generations=len(costs),action_modes=';'.join(modes),
            budget_exhausted=closed['worker_deadline_reached'],closed=True))
    pairs=[]; tasks=[]
    for task in ('random-acts-of-pizza','spooky-author-identification'):
        for seed in sorted({r['seed'] for r in rows if r['task']==task}):
            a=next(r for r in rows if r['seed']==seed and r['arm']=='A')
            b=next(r for r in rows if r['seed']==seed and r['arm']=='B')
            paired=a['initial'] is not None and b['initial'] is not None and abs(a['initial']-b['initial'])<1e-10
            pairs.append(dict(task=task,seed=seed,initials_match=paired,A_gain=a['gain'],B_gain=b['gain'],
                B_minus_A_gain=(b['gain']-a['gain']) if paired and a['gain'] is not None and b['gain'] is not None else None))
        v=[x['B_minus_A_gain'] for x in pairs if x['task']==task and x['B_minus_A_gain'] is not None]
        tasks.append(dict(task=task,paired=len(v),planned=2,median_delta=statistics.median(v) if v else None,
            sample_variance=statistics.variance(v) if len(v)>1 else None,
            B_wins=sum(x>1e-12 for x in v),ties=sum(abs(x)<=1e-12 for x in v),A_wins=sum(x< -1e-12 for x in v)))
    out=R/'readout-v1'; out.mkdir()
    for name,data in [('runs.csv',rows),('actions.csv',actions),('pairs.csv',pairs)]:
        with (out/name).open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0])); writer.writeheader(); writer.writerows(data)
    job=read(R/'launch.json')['job']
    import os
    accounting=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],
        env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25).strip()
    summary=dict(plan_sha256=sha(R/'plan.json'),producer_sha256=sha(Path(__file__)),rows=rows,tasks=tasks,
        numerical_gate=all(t['paired']==2 and t['median_delta']>0 for t in tasks),
        mechanism_gate='NOT_YET_REVIEWED: numerical gains alone cannot pass',
        accounting=accounting,files={n:sha(out/n) for n in ('runs.csv','actions.csv','pairs.csv')},
        scope='exploratory reused D_search, strong old selected starts, 2 generation seeds/task, no independent test or novelty claim')
    write(out/'summary.json',summary); print(json.dumps(summary,sort_keys=True))
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['status','analyze']); a=p.parse_args()
    if a.mode=='status': print(json.dumps(status(),sort_keys=True))
    else: analyze()
