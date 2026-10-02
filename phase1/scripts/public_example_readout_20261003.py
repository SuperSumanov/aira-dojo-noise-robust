"""All-assigned, closed-allocation development readout; never partial efficacy."""
import argparse,csv,hashlib,json,math,os,statistics,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/public-example-feedback-20261003-v1')
PLAN='40e6bc3301c1db52fa09a794577c0b5dc95533302b0e460a044942a6485c5376'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    with p.open('x') as f:json.dump(x,f,sort_keys=True,indent=2,allow_nan=False)
def status():
    assert sha(R/'plan.json')==PLAN
    out=[]
    for s in read(R/'plan.json')['schedule']:
        e=R/f'episode-{s["index"]}'
        out.append(dict(index=s['index'],task=s['task'],arm=s['arm'],seed=s['seed'],wave=s['wave'],
            launched=(e/'launch.json').exists(),closed=(e/'closed.json').exists(),
            generated=len(list(e.glob('action-*/generation.private.json'))),returned=len(list(e.glob('action-*/result.json'))),
            public_packet=(e/'action-0/public-packet.private.json').exists(),
            format_rejects=sum(read(x)['status']!='PASS' for x in e.glob('action-*/format.json')),
            failure=read(e/'failure.json').get('error_type') if (e/'failure.json').exists() else None))
    return dict(job=read(R/'launch.json')['job'] if (R/'launch.json').exists() else None,
        service_ready=(R/'service-ready.json').exists(),all_closed=(R/'all-closed.json').exists(),
        allocation_closed=(R/'closed.json').exists(),controller_error=read(R/'controller-error.json') if (R/'controller-error.json').exists() else None,rows=out)
def compare(runs):
    pairs=[];stats=[]
    for task in sorted({r['task'] for r in runs}):
        for seed in sorted({r['seed'] for r in runs if r['task']==task}):
            arm={r['arm']:r for r in runs if r['seed']==seed};assert set(arm)=={'uniform','contrast'}
            a,b=arm['uniform'],arm['contrast'];initial_equal=a['initial'] is not None and b['initial'] is not None and abs(a['initial']-b['initial'])<1e-10
            diagnostic_equal=a['diagnostic_prediction_sha256'] is not None and a['diagnostic_prediction_sha256']==b['diagnostic_prediction_sha256'] and a['public_labels_sha256']==b['public_labels_sha256']
            paired=initial_equal and diagnostic_equal and a['closed'] and b['closed']
            pairs.append(dict(task=task,seed=seed,initial_equal=initial_equal,diagnostic_equal=diagnostic_equal,comparable=paired,
                uniform_gain=a['gain'],contrast_gain=b['gain'],contrast_minus_uniform=b['gain']-a['gain'] if paired else None))
        values=[r['contrast_minus_uniform'] for r in pairs if r['task']==task and r['comparable']]
        stats.append(dict(task=task,paired=len(values),median_delta=statistics.median(values) if values else None,
            sample_variance=statistics.variance(values) if len(values)>1 else None,
            contrast_wins=sum(v>0 for v in values),uniform_wins=sum(v<0 for v in values),ties=sum(v==0 for v in values),
            improved_candidates=sum(r['improved_candidates'] or 0 for r in runs if r['task']==task)))
    gate=all(t['paired']==2 and t['median_delta']>0 and t['uniform_wins']==0 and t['improved_candidates']>0 for t in stats)
    return pairs,stats,gate
def analyze():
    assert sha(R/'plan.json')==PLAN and read(R/'closed.json')['service_closed']
    p=read(R/'plan.json')
    for rel,h in p['files'].items():assert sha(R/rel)==h
    runs=[];actions=[];inputs={}
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}';seen=[];first=None;metadata={}
        finished=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        closed=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        choose=min if s['start']==1 else max;direction=-1 if s['start']==1 else 1
        for step in range(7):
            a=ep/f'action-{step}';result=read(a/'result.json') if (a/'result.json').exists() else None
            gen=read(a/'generation.private.json') if (a/'generation.private.json').exists() else None
            form=read(a/'format.json') if (a/'format.json').exists() else None
            st=read(a/'started.json') if (a/'started.json').exists() else None
            if result:
                assert result['elapsed_seconds']<=900 and result['step']==step
                if result['valid']:
                    assert result['kind']=='SOLUTION' and result['execution_success'] and math.isfinite(result['metric'])
                    seen.append((result['metric'],step))
                    if step==0:first=result['metric']
                best=choose(seen,key=lambda x:x[0]) if seen else (None,None)
                assert result['selected_metric']==best[0] and result['selected_step']==best[1]
            if step==0 and (a/'public-packet.private.json').exists():metadata=read(a/'public-packet.private.json')['metadata']
            for name in ('result.json','started.json','executed.json','replay.json','binding.json','generation.private.json','request.private.json','node.private.json','submission.private.csv','score-receipt.private.json','public-packet.private.json'):
                if (a/name).exists():inputs[str((a/name).relative_to(R))]=sha(a/name)
            actions.append(dict(index=s['index'],task=s['task'],arm=s['arm'],seed=s['seed'],step=step,
                requested=(a/'request.private.json').exists(),generated=gen is not None,generation_seconds=gen['generation_seconds'] if gen else None,
                prompt_tokens=gen.get('usage',{}).get('prompt_tokens') if gen else None,completion_tokens=gen.get('usage',{}).get('completion_tokens') if gen else None,
                format_status=form['status'] if form else None,started=st is not None,returned=result is not None,
                kind=result['kind'] if result else st['kind'] if st else None,valid=result['valid'] if result else False,
                metric=result['metric'] if result else None,execution_success=result['execution_success'] if result else None,
                execution_wall_seconds=result['execution_wall_seconds'] if result else None,replay_seconds=result['replay_seconds'] if result else None,
                elapsed_seconds=result['elapsed_seconds'] if result else None))
        best=choose(seen,key=lambda x:x[0]) if seen else (None,None);aa=[a for a in actions if a['index']==s['index']]
        runs.append(dict(**s,base_commit=p['base_commit'],plan_sha256=PLAN,config_sha256=sha(R/'configs'/f'{s["index"]}.json'),
            run_seconds=900,max_calls=6,max_tokens_per_call=4096,generator='Qwen3.8-27B local AWQ INT4',hardware='gpu28 RTX3090',
            launched=(ep/'launch.json').exists(),closed=bool(closed),worker_status=finished.get('status','no_finished_receipt'),
            budget_exhausted=closed.get('worker_deadline_reached',False) or finished.get('status')=='budget_exhausted',
            initial=first,selected=best[0],selected_step=best[1],gain=direction*(best[0]-first) if first is not None else None,
            valid_candidates=sum(step>0 for v,step in seen),improved_candidates=sum(direction*(v-first)>1e-12 for v,step in seen if step>0) if first is not None else None,
            calls_attempted=sum(a['requested'] for a in aa),calls_completed=sum(a['generated'] for a in aa),
            format_rejects=sum(a['format_status']=='REJECT' for a in aa),unreturned_executions=sum(a['started'] and not a['returned'] for a in aa),
            successful_checks=sum(a['kind']=='CHECK' and a['execution_success'] is True for a in aa),
            diagnostic_prediction_sha256=metadata.get('predictions_sha256'),public_labels_sha256=metadata.get('labels_sha256'),
            shown_sha256=metadata.get('shown_sha256'),mean_selected_public_loss=metadata.get('mean_selected_loss')))
    pairs,stats,gate=compare(runs);all_closed=(R/'all-closed.json').exists();gate=gate and all_closed
    account=subprocess.check_output(['sacct','-X','-j',read(R/'launch.json')['job'],'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25).strip()
    out=R/'readout-v1';out.mkdir()
    for name,data in [('runs.csv',runs),('actions.csv',actions),('pairs.csv',pairs)]:
        with (out/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    result=dict(plan_sha256=PLAN,producer_sha256=sha(Path(__file__)),runs=runs,tasks=stats,pairs=pairs,all_closed=all_closed,numerical_gate=gate,
        mechanism_gate='not certified by score; requires trace review',accounting=account,files={n:sha(out/n) for n in ('runs.csv','actions.csv','pairs.csv')},input_hashes=inputs,limitations=p['limitations'])
    write(out/'summary.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('runs','pairs','input_hashes')},sort_keys=True))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['status','analyze']);x=a.parse_args()
    if x.mode=='status':print(json.dumps(status(),sort_keys=True))
    else:analyze()
