"""All-assigned twelve-trajectory information intervention; closed-all readout."""
import argparse,csv,hashlib,json,math,os,statistics,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/opportunity-information-20261003-v2');PLAN='6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def status():
    assert sha(R/'plan.json')==PLAN;rr=[]
    for s in read(R/'plan.json')['schedule']:
        ep=R/f'episode-{s["index"]}'
        rr.append(dict(index=s['index'],task=s['task'],arm=s['arm'],wave=s['wave'],launched=(ep/'native.json').exists(),closed=(ep/'closed.json').exists(),
            requests=len(list(ep.glob('action-*/request.private.json'))),generated=len(list(ep.glob('action-*/generation.private.json'))),returned=len(list(ep.glob('action-*/result.json'))),
            format_rejects=sum(read(p)['status']=='REJECT' for p in ep.glob('action-*/format.json')),
            failure=read(ep/'failure.json')['error_type'] if (ep/'failure.json').exists() else None))
    print(json.dumps(dict(job=read(R/'launch.json')['job'] if (R/'launch.json').exists() else None,service_ready=(R/'service-ready.json').exists(),
        all_closed=(R/'all-closed.json').exists(),closed=(R/'closed.json').exists(),controller_error=read(R/'controller-error.json') if (R/'controller-error.json').exists() else None,rows=rr)))
def compare(runs):
    pairs=[];stats=[]
    for task in sorted({r['task'] for r in runs}):
        for seed in sorted({r['seed'] for r in runs if r['task']==task}):
            d={r['arm']:r for r in runs if r['task']==task and r['seed']==seed};assert set(d)==set('ABC');a,b,c=[d[k] for k in 'ABC']
            equal=all(r['initial'] is not None and r['initial_sha256'] is not None and r['closed'] for r in (a,b,c))
            equal=equal and len({r['initial_sha256'] for r in (a,b,c)})==1 and max(r['initial'] for r in (a,b,c))-min(r['initial'] for r in (a,b,c))<1e-11
            pairs.append(dict(task=task,seed=seed,comparable=equal,A_gain=a['gain'],B_gain=b['gain'],C_gain=c['gain'],
                B_minus_A=b['gain']-a['gain'] if equal else None,C_minus_A=c['gain']-a['gain'] if equal else None,C_minus_B=c['gain']-b['gain'] if equal else None))
        for contrast in ('B_minus_A','C_minus_A','C_minus_B'):
            vals=[p[contrast] for p in pairs if p['task']==task and p['comparable']]
            stats.append(dict(task=task,contrast=contrast,paired=len(vals),values=vals,median=statistics.median(vals) if vals else None,
                sample_variance=statistics.variance(vals) if len(vals)>1 else None,positive=sum(v>1e-12 for v in vals),negative=sum(v< -1e-12 for v in vals),ties=sum(abs(v)<=1e-12 for v in vals)))
    bs=[x for x in stats if x['contrast']=='B_minus_A']
    gate=len(bs)==2 and all(x['paired']==2 and x['median']>0 and x['negative']==0 and any(r['arm']=='B' and r['task']==x['task'] and (r['improved_candidates'] or 0)>0 for r in runs) for x in bs)
    return pairs,stats,gate
def freeze():
    assert sha(R/'plan.json')==PLAN and not (R/'readout-v1').exists()
    # Positive/negative synthetic contrasts and missing-initial rejection.
    rr=[dict(task=t,seed=i,arm=a,initial=1.,initial_sha256='same',closed=True,gain=g,improved_candidates=int(g>0)) for t in ('p','s') for i in (0,1) for a,g in [('A',0),('B',.1),('C',.2)]]
    pp,ss,gate=compare(rr);assert gate and all(abs(x['B_minus_A']-.1)<1e-12 for x in pp)
    rr[1]['initial']=None;assert not compare(rr)[2]
    write(R/'readout-freeze.json',dict(plan_sha256=PLAN,script_sha256=sha(Path(__file__)),fixtures=2,utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()));print('READOUT_FROZEN')
def analyze():
    assert sha(R/'plan.json')==PLAN and read(R/'readout-freeze.json')['script_sha256']==sha(Path(__file__))
    assert read(R/'closed.json')['service_closed'] and not (R/'readout-v1').exists()
    p=read(R/'plan.json')
    for f,h in p['files'].items():assert sha(R/f)==h
    runs=[];actions=[];inputs={}
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}';first=None;first_sha=None;seen=[];choose=min if s['start']==1 else max;direction=-1 if s['start']==1 else 1
        finished=read(ep/'finished.json') if (ep/'finished.json').exists() else {};closed=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        for step in range(5):
            a=ep/f'action-{step}';r=read(a/'result.json') if (a/'result.json').exists() else None;g=read(a/'generation.private.json') if (a/'generation.private.json').exists() else None
            fmt=read(a/'format.json') if (a/'format.json').exists() else None;st=read(a/'started.json') if (a/'started.json').exists() else None
            if r:
                assert r['elapsed_seconds']<=600 and r['step']==step
                if r['valid']:
                    assert r['kind']=='SOLUTION' and r['execution_success'] and math.isfinite(r['metric']);seen.append((r['metric'],step))
                    if step==0:first=r['metric'];first_sha=sha(a/'submission.private.csv')
                best=choose(seen,key=lambda x:x[0]) if seen else (None,None);assert r['selected_metric']==best[0] and r['selected_step']==best[1]
            for file in ('result.json','started.json','replay.json','binding.json','request.private.json','generation.private.json','node.private.json','submission.private.csv','score-receipt.private.json'):
                if (a/file).exists():inputs[str((a/file).relative_to(R))]=sha(a/file)
            actions.append(dict(index=s['index'],task=s['task'],arm=s['arm'],seed=s['seed'],step=step,requested=(a/'request.private.json').exists(),generated=g is not None,
                generation_seconds=g['generation_seconds'] if g else None,prompt_tokens=g.get('usage',{}).get('prompt_tokens') if g else None,completion_tokens=g.get('usage',{}).get('completion_tokens') if g else None,
                format_status=fmt['status'] if fmt else None,started=st is not None,returned=r is not None,kind=r['kind'] if r else st['kind'] if st else None,
                valid=r['valid'] if r else False,metric=r['metric'] if r else None,execution_success=r['execution_success'] if r else None,
                execution_seconds=r['execution_wall_seconds'] if r else None,replay_seconds=r['replay_seconds'] if r else None,elapsed_seconds=r['elapsed_seconds'] if r else None))
        best=choose(seen,key=lambda x:x[0]) if seen else (None,None);aa=[a for a in actions if a['index']==s['index']]
        runs.append(dict(**s,commit=p['base_commit'],plan_sha256=PLAN,config_sha256=sha(R/'configs'/f'{s["index"]}.json'),run_seconds=600,max_calls=4,max_tokens=4096,
            launched=(ep/'launch.json').exists(),closed=bool(closed),worker_status=finished.get('status','no_finished_receipt'),budget_exhausted=bool(closed.get('worker_deadline_reached')) or finished.get('status')=='budget_exhausted',
            initial=first,initial_sha256=first_sha,selected=best[0],selected_step=best[1],gain=direction*(best[0]-first) if first is not None else None,
            valid_candidates=sum(step>0 for _,step in seen),improved_candidates=sum(direction*(v-first)>1e-12 for v,step in seen if step>0) if first is not None else None,
            calls_attempted=sum(a['requested'] for a in aa),calls_completed=sum(a['generated'] for a in aa),format_rejects=sum(a['format_status']=='REJECT' for a in aa),
            unreturned_executions=sum(a['started'] and not a['returned'] for a in aa),successful_checks=sum(a['kind']=='CHECK' and a['execution_success'] is True for a in aa)))
    pairs,stats,gate=compare(runs);gate=gate and (R/'all-closed.json').exists()
    job=read(R/'launch.json')['job'];text=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    fields=next(x for x in text.splitlines() if x.split('|')[0]==job).split('|');assert fields[1] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED') and 'gres/gpu=4' in fields[3]
    account=dict(job=job,state=fields[1],elapsed_seconds=int(fields[2]),gpus=4,gpu_hours=int(fields[2])*4/3600,exit_code=fields[4]);assert account['gpu_hours']<=6
    out=R/'readout-v1';out.mkdir()
    for name,data in [('runs.csv',runs),('actions.csv',actions),('pairs.csv',pairs)]:
        with (out/name).open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    summary=dict(plan_sha256=PLAN,readout_sha256=sha(Path(__file__)),runs=runs,contrasts=stats,pairs=pairs,numerical_B_gate=gate,
        mechanism_gate='not established by numeric gate; actual trace and independent metric checks required',accounting=account,input_hashes=inputs,files={f:sha(out/f) for f in ('runs.csv','actions.csv','pairs.csv')},
        limitations=p['information']+' '+p['selection']+' '+p['cost'])
    write(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k not in ('runs','pairs','input_hashes')}))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','status','analyze']);globals()[a.parse_args().mode]()
