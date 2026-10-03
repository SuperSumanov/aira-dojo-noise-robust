"""Frozen all-assigned fresh-root qualification readout; no partial effects."""
import argparse,csv,datetime,hashlib,json,math,os,statistics,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-gpu1-v3')
PLAN='b4dd6a7a59000b90ee2307b8038b1c013864ab66eef614b6eecb7c64feb0b4c5'

def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)

def status():
    assert sha(R/'plan.json')==PLAN
    rr=[]
    for s in read(R/'plan.json')['schedule']:
        ep=R/f'episode-{s["index"]}'
        rr.append(dict(index=s['index'],role=s['role'],task=s['task'],arm=s['arm'],wave=s['wave'],launched=(ep/'native.json').exists(),closed=(ep/'closed.json').exists(),requests=len(list(ep.glob('action-*/request.private.json'))),generated=len(list(ep.glob('action-*/generation.private.json'))),returned=len(list(ep.glob('action-*/result.json'))),plan_actions=len(list(ep.glob('action-*/plan.private.json'))),failure=read(ep/'failure.json')['error_type'] if (ep/'failure.json').exists() else None))
    print(json.dumps(dict(job=read(R/'launch.json')['job'] if (R/'launch.json').exists() else None,service_ready=(R/'service-ready.json').exists(),roots_ready=(R/'roots-ready.json').exists(),roots_unavailable=(R/'roots-unavailable.json').exists(),all_closed=(R/'all-closed.json').exists(),closed=(R/'closed.json').exists(),controller_error=read(R/'controller-error.json') if (R/'controller-error.json').exists() else None,rows=rr)))

def compare(runs):
    runs=[r for r in runs if r['role']=='comparison'];pairs=[];stats=[]
    for task in sorted({r['task'] for r in runs}):
        for seed in sorted({r['seed'] for r in runs if r['task']==task}):
            dd={r['arm']:r for r in runs if r['task']==task and r['seed']==seed};assert set(dd)==set('ABC')
            a,b,c=[dd[k] for k in 'ABC']
            equal=all(r['initial'] is not None and r['initial_sha256'] is not None and r['closed'] and r['gain'] is not None for r in (a,b,c))
            equal=equal and len({r['initial_sha256'] for r in (a,b,c)})==1 and max(r['initial'] for r in (a,b,c))-min(r['initial'] for r in (a,b,c))<1e-11
            pairs.append(dict(task=task,seed=seed,comparable=equal,A_gain=a['gain'],B_gain=b['gain'],C_gain=c['gain'],B_minus_A=b['gain']-a['gain'] if equal else None,B_minus_C=b['gain']-c['gain'] if equal else None,C_minus_A=c['gain']-a['gain'] if equal else None))
        for contrast in ('B_minus_A','B_minus_C','C_minus_A'):
            vv=[p[contrast] for p in pairs if p['task']==task and p['comparable']]
            stats.append(dict(task=task,contrast=contrast,paired=len(vv),values=vv,median=statistics.median(vv) if vv else None,sample_variance=statistics.variance(vv) if len(vv)>1 else None,positive=sum(v>0 for v in vv),negative=sum(v<0 for v in vv),ties=sum(v==0 for v in vv)))
    checks=[r for r in stats if r['contrast'] in ('B_minus_A','B_minus_C')]
    gate=len(pairs)==4 and len(checks)==4 and all(p['comparable'] for p in pairs) and all(r['paired']==2 and r['median']>0 and r['negative']==0 and any(x['arm']=='B' and x['task']==r['task'] and (x['improved_candidates'] or 0)>0 for x in runs) for r in checks)
    return pairs,stats,gate

def fixtures():
    rr=[dict(role='comparison',task=t,seed=i,arm=a,initial=1.,initial_sha256='same',closed=True,gain=g,improved_candidates=int(g>0)) for t in ('p','s') for i in (0,1) for a,g in [('A',0),('B',.2),('C',.1)]]
    assert compare(rr)[2]
    rr[1]['gain']=.05;assert not compare(rr)[2] # one seed below rule reference
    rr[1]['gain']=.2;rr[1]['initial']=None;assert not compare(rr)[2]
    assert compare(rr)[0][0]['B_minus_A'] is None
    rr[1]['initial']=1;rr[1]['initial_sha256']='other';assert not compare(rr)[2]
    rr[1]['initial_sha256']='same';rr[1]['closed']=False;assert not compare(rr)[2]
    for r in rr:r.update(initial=None,initial_sha256=None,gain=None,closed=False)
    assert not compare(rr)[2] and all(p['B_minus_C'] is None for p in compare(rr)[0])
    return 6

def freeze():
    assert sha(R/'plan.json')==PLAN and not (R/'readout-v1').exists()
    n=fixtures();write(R/'readout-freeze.json',dict(plan_sha256=PLAN,script_sha256=sha(Path(__file__)),fixtures=n,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    print('READOUT_FROZEN')

def analyze():
    assert sha(R/'plan.json')==PLAN and read(R/'readout-freeze.json')['script_sha256']==sha(Path(__file__))
    assert read(R/'closed.json')['service_closed'] and not (R/'readout-v1').exists()
    p=read(R/'plan.json')
    for f,h in p['files'].items():assert sha(R/f)==h
    runs=[];actions=[];inputs={}
    def remember(f):
        if f.exists():inputs[str(f.relative_to(R))]=sha(f)
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}';first=None;first_sha=None;seen=[];choose=min if s['start']==1 else max;direction=-1 if s['start']==1 else 1
        finished=read(ep/'finished.json') if (ep/'finished.json').exists() else {};closed=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        for step in range(5):
            a=ep/f'action-{step}';r=read(a/'result.json') if (a/'result.json').exists() else None;g=read(a/'generation.private.json') if (a/'generation.private.json').exists() else None
            fmt=read(a/'format.json') if (a/'format.json').exists() else None;st=read(a/'started.json') if (a/'started.json').exists() else None;plan=(a/'plan.private.json').exists()
            if plan:assert r is None and st is None and fmt['mode']=='PLAN' and step in (1,2,3)
            if r:
                assert r['elapsed_seconds']<=600 and r['step']==step
                if r['valid']:
                    assert r['kind']=='SOLUTION' and r['execution_success'] and math.isfinite(r['metric']);seen.append((r['metric'],step))
                    if step==0:first=r['metric'];first_sha=sha(a/'submission.private.csv')
                best=choose(seen,key=lambda x:x[0]) if seen else (None,None);assert r['selected_metric']==best[0] and r['selected_step']==best[1]
            for file in ('result.json','started.json','replay.json','binding.json','request.private.json','generation.private.json','plan.private.json','format.json','node.private.json','submission.private.csv','score-receipt.private.json'):remember(a/file)
            actions.append(dict(index=s['index'],role=s['role'],task=s['task'],arm=s['arm'],seed=s['seed'],step=step,requested=(a/'request.private.json').exists(),generated=g is not None,plan_action=plan,generation_seconds=g['generation_seconds'] if g else None,prompt_tokens=g.get('usage',{}).get('prompt_tokens') if g else None,completion_tokens=g.get('usage',{}).get('completion_tokens') if g else None,format_status=fmt['status'] if fmt else None,started=st is not None,returned=r is not None,kind=r['kind'] if r else st['kind'] if st else fmt['mode'] if fmt and fmt['status']=='PASS' else None,valid=r['valid'] if r else False,metric=r['metric'] if r else None,execution_success=r['execution_success'] if r else None,execution_seconds=r['execution_wall_seconds'] if r else None,replay_seconds=r['replay_seconds'] if r else None,elapsed_seconds=r['elapsed_seconds'] if r else None))
        best=choose(seen,key=lambda x:x[0]) if seen else (None,None);aa=[a for a in actions if a['index']==s['index']]
        for file in ('native.json','finished.json','closed.json','first-valid.json','seed-program.private.json'):remember(ep/file)
        if s['role']=='root':
            assert not (ep/'action-0').exists() and len(seen)<=1
            if seen:assert read(ep/'first-valid.json')['step']==seen[0][1]
        runs.append(dict(**s,commit=p['base_commit'],plan_sha256=PLAN,config_sha256=sha(R/'configs'/f'{s["index"]}.json'),run_seconds=600,max_calls=4,max_tokens=4096,launched=(ep/'native.json').exists(),closed=bool(closed),worker_status=finished.get('status','no_finished_receipt'),budget_exhausted=bool(closed.get('worker_deadline_reached')) or finished.get('status')=='budget_exhausted',initial=first,initial_sha256=first_sha,selected=best[0],selected_step=best[1],gain=direction*(best[0]-first) if first is not None else None,valid_candidates=sum(step>0 for _,step in seen),improved_candidates=sum(direction*(v-first)>0 for v,step in seen if step>0) if first is not None else None,calls_attempted=sum(a['requested'] for a in aa),calls_completed=sum(a['generated'] for a in aa),plan_actions=sum(a['plan_action'] for a in aa),format_rejects=sum(a['format_status']=='REJECT' for a in aa),unreturned_executions=sum(a['started'] and not a['returned'] for a in aa),successful_checks=sum(a['kind']=='CHECK' and a['execution_success'] is True for a in aa)))
        assert runs[-1]['calls_attempted']<=4
    for file in ('roots-ready.json','roots-unavailable.json','closed.json','all-closed.json','service-ready.json','service-native.json'):remember(R/file)
    pairs,stats,gate=compare(runs);gate=gate and (R/'all-closed.json').exists() and (R/'roots-ready.json').exists()
    job=read(R/'launch.json')['job'];txt=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    fields=next(x for x in txt.splitlines() if x.split('|')[0]==job).split('|');assert fields[1] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED') and 'gres/gpu=4' in fields[3]
    account=dict(job=job,state=fields[1],elapsed_seconds=int(fields[2]),gpus=4,gpu_hours=int(fields[2])*4/3600,exit_code=fields[4])
    prior=read(R/'prior-accounting.json');account['prior_jobs']=prior['jobs'];account['prior_gpu_hours']=prior['gpu_hours'];account['total_gpu_hours']=account['gpu_hours']+prior['gpu_hours']
    account['budget_exceeded']=account['total_gpu_hours']>8;gate=gate and not account['budget_exceeded']
    out=R/'readout-v1';out.mkdir()
    for name,data in [('runs.csv',runs),('actions.csv',actions),('pairs.csv',pairs)]:
        with (out/name).open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    summary=dict(plan_sha256=PLAN,readout_sha256=sha(Path(__file__)),runs=runs,contrasts=stats,pairs=pairs,numerical_B_gate=gate,root_availability_gate=(R/'roots-ready.json').exists(),mechanism_gate='Not determined by numbers: independently inspect automatic plan implementation and known-rule rediscovery. No new-method claim.',accounting=account,input_hashes=inputs,files={f:sha(out/f) for f in ('runs.csv','actions.csv','pairs.csv')},limitations=p['limitations']+' '+p['selection']+' '+p['cost'])
    write(out/'summary.json',summary);print(json.dumps({k:v for k,v in summary.items() if k not in ('runs','pairs','input_hashes')}))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['freeze','status','analyze','fixtures']);globals()[a.parse_args().mode]()
