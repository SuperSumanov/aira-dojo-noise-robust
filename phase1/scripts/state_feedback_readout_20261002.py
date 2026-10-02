"""Frozen, all-assigned Pizza factorial readout. No partial efficacy readout."""
import argparse,csv,hashlib,json,math,os,statistics,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/state-feedback-pizza-20261002-v1')
PLAN='4b95fcc575c2f8fa438bd3737d05ec6f40ffa0aa2bfdfc89de38e76e71979b5b'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def status():
    assert sha(R/'plan.json')==PLAN
    out=[]
    for s in read(R/'plan.json')['schedule']:
        e=R/f'episode-{s["index"]}'
        out.append(dict(index=s['index'],arm=s['arm'],seed=s['seed'],wave=s['wave'],
            launched=(e/'launch.json').exists(),closed=(e/'closed.json').exists(),
            generated=len(list(e.glob('action-*/generation.private.json'))),
            returned=len(list(e.glob('action-*/result.json'))),
            format_rejects=sum(read(x)['status']!='PASS' for x in e.glob('action-*/format.json')),
            replay_failures=sum(not read(x)['success'] for x in e.glob('action-*/replay.json')),
            generation_failures=len(list(e.glob('action-*/generation_failed.json'))),
            failure=read(e/'failure.json').get('error_type') if (e/'failure.json').exists() else None))
    return dict(job=read(R/'launch.json')['job'] if (R/'launch.json').exists() else None,
        claim=(R/'claim.json').exists(),service_ready=(R/'service-ready.json').exists(),
        all_closed=(R/'all-closed.json').exists(),allocation_closed=(R/'closed.json').exists(),rows=out)
def contrasts(rows):
    pairs=[]
    for seed in sorted({r['seed'] for r in rows}):
        a={r['arm']:r for r in rows if r['seed']==seed}
        assert set(a)==set('ABCD')
        comparable=all(v['initial'] is not None and v['gain'] is not None for v in a.values())
        if comparable:comparable=max(v['initial'] for v in a.values())-min(v['initial'] for v in a.values())<1e-10
        g={k:v['gain'] for k,v in a.items()}
        pairs.append(dict(seed=seed,initials_match=comparable,
            **{k+'_gain':v for k,v in g.items()},
            interaction=(g['D']-g['B'])-(g['C']-g['A']) if comparable else None,
            D_minus_C=g['D']-g['C'] if comparable else None,
            D_minus_B=g['D']-g['B'] if comparable else None,
            B_minus_A=g['B']-g['A'] if comparable else None,
            C_minus_A=g['C']-g['A'] if comparable else None))
    stats={}
    for k in ('interaction','D_minus_C','D_minus_B','B_minus_A','C_minus_A'):
        v=[r[k] for r in pairs if r[k] is not None]
        stats[k]=dict(n=len(v),median=statistics.median(v) if v else None,
            sample_variance=statistics.variance(v) if len(v)>1 else None,
            positive=sum(x>1e-12 for x in v),tie=sum(abs(x)<=1e-12 for x in v),negative=sum(x< -1e-12 for x in v))
    gate=all(stats[k]['n']==2 and stats[k]['median']>0 for k in ('interaction','D_minus_C','D_minus_B'))
    return pairs,stats,gate
def analyze():
    assert sha(R/'plan.json')==PLAN
    p=read(R/'plan.json');assert (R/'all-closed.json').exists() and read(R/'closed.json')['service_closed']
    for rel,h in p['files'].items():assert sha(R/rel)==h
    runs=[];actions=[];bindings={}
    for s in p['schedule']:
        e=R/f'episode-{s["index"]}';closed=read(e/'closed.json');seen=[];first=None
        finished=read(e/'finished.json') if (e/'finished.json').exists() else {}
        for step in range(5):
            a=e/f'action-{step}';q=a/'result.json';r=read(q) if q.exists() else None
            gen=read(a/'generation.private.json') if (a/'generation.private.json').exists() else None
            replay=read(a/'replay.json') if (a/'replay.json').exists() else None
            form=read(a/'format.json') if (a/'format.json').exists() else None
            started=read(a/'started.json') if (a/'started.json').exists() else None
            if r:
                assert r['elapsed_seconds']<=p['run_seconds'] and r['step']==step
                assert r['retained']==s['retained'] and r['visible']==s['visible']
                if r['valid']:
                    assert r['kind']=='SOLUTION' and r['execution_success'] and math.isfinite(r['metric'])
                    seen.append((r['metric'],step))
                    if step==0:first=r['metric']
                best=max(seen,key=lambda x:x[0]) if seen else (None,None)
                assert r['selected_metric']==best[0] and r['selected_step']==best[1]
            for name in ('result.json','started.json','replay.json','binding.json','generation.private.json','request.private.json','node.private.json','submission.private.csv','score-receipt.private.json'):
                if (a/name).exists():bindings[str((a/name).relative_to(R))]=sha(a/name)
            actions.append(dict(index=s['index'],arm=s['arm'],seed=s['seed'],step=step,
                requested=(a/'request.private.json').exists(),generated=gen is not None,
                generation_seconds=gen['generation_seconds'] if gen else None,
                completion_tokens=gen.get('usage',{}).get('completion_tokens') if gen else None,
                format_status=form['status'] if form else None,format_error=form.get('error_type') if form else None,
                started=started is not None,returned=r is not None,
                replay_attempted=replay is not None,replay_success=replay['success'] if replay else None,
                replay_seconds=replay['seconds'] if replay else 0,
                kind=r['kind'] if r else started['kind'] if started else None,
                valid=r['valid'] if r else False,metric=r['metric'] if r else None,
                execution_success=r['execution_success'] if r else None,
                execution_wall_seconds=r['execution_wall_seconds'] if r else None,
                timed_out=r['timed_out'] if r else None,elapsed_seconds=r['elapsed_seconds'] if r else None))
        best=max(seen,key=lambda x:x[0]) if seen else (None,None)
        aa=[v for v in actions if v['index']==s['index']]
        runs.append(dict(**s,base_commit=p['base_commit'],plan_sha256=PLAN,
            config_sha256=sha(R/'configs'/f'{s["index"]}.json'),run_seconds=p['run_seconds'],
            max_calls=p['max_calls'],max_tokens_per_call=p['max_tokens_per_call'],
            generator='Qwen3.8-27B local AWQ INT4',hardware='gpu28 RTX3090',
            initial=first,selected=best[0],selected_step=best[1],gain=best[0]-first if first is not None else None,
            valid_candidates=len(seen)-int(first is not None),
            improved_candidates=sum(v>first+1e-12 for v,step in seen if step>0) if first is not None else None,
            calls_attempted=sum(a['requested'] for a in aa),calls_completed=sum(a['generated'] for a in aa),
            completed_generation_seconds=sum(a['generation_seconds'] or 0 for a in aa),
            replay_seconds=sum(a['replay_seconds'] for a in aa),
            returned_execution_seconds=sum(a['execution_wall_seconds'] or 0 for a in aa),
            unreturned_executions=sum(a['started'] and not a['returned'] for a in aa),
            successful_checks=sum(a['kind']=='CHECK' and a['execution_success'] is True for a in aa),
            worker_status=finished.get('status','no_finished_receipt'),
            budget_exhausted=closed['worker_deadline_reached'] or finished.get('status')=='budget_exhausted'))
    assert len(runs)==8
    pairs,stats,gate=contrasts(runs)
    accounting=subprocess.check_output(['sacct','-X','-j',read(R/'launch.json')['job'],'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25).strip()
    out=R/'readout-v1';out.mkdir()
    for name,data in [('runs.csv',runs),('actions.csv',actions),('pairs.csv',pairs)]:
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    summary=dict(plan_sha256=PLAN,producer_sha256=sha(Path(__file__)),runs=runs,contrasts=stats,
        numerical_gate=gate,mechanism_gate='not certified by scores; separate trace review required',
        accounting=accounting,files={n:sha(out/n) for n in ('runs.csv','actions.csv','pairs.csv')},
        input_hashes=bindings,limitations=p['limitations'],
        scope='all eight assigned; incumbent gain within registered budget; missing initial is not zero; ordinary persistent D is strong reference, not a new method; duration components with unfinished work are censored')
    write(out/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('input_hashes','runs')},sort_keys=True))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['status','analyze']);x=a.parse_args()
    if x.mode=='status':print(json.dumps(status(),sort_keys=True))
    else:analyze()
