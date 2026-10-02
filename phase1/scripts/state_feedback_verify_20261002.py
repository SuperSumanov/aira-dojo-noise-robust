"""Independent pair-count AUC and factorial algebra, no model execution."""
import csv,hashlib,json,math,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/state-feedback-pizza-20261002-v1')
PLAN='4b95fcc575c2f8fa438bd3737d05ec6f40ffa0aa2bfdfc89de38e76e71979b5b'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def close(x,y):
    return x is None and y is None or x is not None and y is not None and math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-11)
def auc(y,p):
    pos=[v for k,v in p.items() if int(y[k]['requester_received_pizza'])==1]
    neg=[v for k,v in p.items() if int(y[k]['requester_received_pizza'])==0]
    assert pos and neg and all(math.isfinite(v) for v in p.values())
    return math.fsum(1 if a>b else .5 if a==b else 0 for a in pos for b in neg)/(len(pos)*len(neg))
def main():
    assert sha(R/'plan.json')==PLAN
    sys.path.insert(0,str(R));from task_feedback_real_20261001 import m
    p=m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    summary=read(R/'readout-v1/summary.json');assert summary['plan_sha256']==PLAN
    for n,h in summary['files'].items():assert sha(R/'readout-v1'/n)==h
    for n,h in summary['input_hashes'].items():assert sha(R/n)==h
    assert read(R/'closed.json')['service_closed'] and (R/'all-closed.json').exists()
    service=read(R/'service-native.json');job=read(R/'launch.json')['job'];assert service['job']==job
    reported={r['index']:r for r in summary['runs']};actual=[];valid=0;checks=[];binding_count=0
    for s in p['schedule']:
        e=R/f'episode-{s["index"]}';assert (e/'closed.json').exists()
        n=read(e/'native.json');assert n['job']==job and len(n['gpu_uuids'])==1
        assert not set(n['gpu_uuids'])&set(service['gpu_uuids'])
        assert n['config_sha256']==sha(R/'configs'/f'{s["index"]}.json')
        cfg=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json')
        task=MLEBenchTask(cfg.task);spec=task._search_only_module.SPEC[s['task']]
        data=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv')
        truth={r['request_id']:r for r in data};assert len(truth)==len(data)
        values=[];first=None;ledger=[];previous=[];calls=0;retired=False
        for step in range(5):
            a=e/f'action-{step}';req=a/'request.private.json'
            if req.exists():
                calls+=1;q=read(req);assert q['seed']==s['seed']*10+step
                assert step>0 and q['step']==step
                for old_step,old,oldnode in previous:
                    returned=oldnode['terminal'][-12000:] if old_step>0 or s['visible'] else '[initial program stdout withheld; future tool returns remain available]'
                    assert returned in q['prompt'] and oldnode['plan'] in q['prompt']
                    assert f"Exit={old['exit_code']}; timed_out={old['timed_out']}" in q['prompt']
                for c in ledger:assert c in q['prompt']
                checks.append(dict(index=s['index'],step=step,prior_returns_checked=len(previous),ledger_cells=len(ledger)))
            if (a/'binding.json').exists():
                b=read(a/'binding.json');assert b['system_bindpaths_disabled'] and b['namespace']['exact_device_namespace'];binding_count+=1
            if not (a/'result.json').exists():continue
            r=read(a/'result.json');node=read(a/'node.private.json');st=read(a/'started.json')
            assert hashlib.sha256(node['code'].encode()).hexdigest()==r['code_sha256']==st['code_sha256']
            assert r['step']==step and r['elapsed_seconds']<=720
            if step==0:assert r['code_sha256']==p['starts'][0]['code_sha256']
            if r['kind']=='CHECK':assert not r['valid'] and r['metric'] is None
            if r['execution_success']:ledger.append(node['code'])
            assert r['successful_ledger_cells']==len(ledger)
            if r['valid']:
                assert r['kind']=='SOLUTION' and r['exit_code']==0 and not r['timed_out']
                predrows=rows(a/'submission.private.csv')
                pred={row['request_id']:float(row['requester_received_pizza']) for row in predrows}
                assert len(pred)==len(predrows)==len(truth) and set(pred)==set(truth)
                v=auc(truth,pred);assert close(v,r['metric']);values.append(v);valid+=1
                if step==0:first=v
            assert close(max(values) if values else None,r['selected_metric'])
            previous.append((step,r,node))
        assert calls<=4 and calls==reported[s['index']]['calls_attempted']
        best=max(values) if values else None;gain=best-first if first is not None else None
        for k,v in [('initial',first),('selected',best),('gain',gain)]:assert close(v,reported[s['index']][k])
        actual.append(dict(seed=s['seed'],arm=s['arm'],initial=first,gain=gain))
    contrasts={k:[] for k in ('interaction','D_minus_C','D_minus_B','B_minus_A','C_minus_A')}
    for seed in sorted({r['seed'] for r in actual}):
        a={r['arm']:r for r in actual if r['seed']==seed};assert set(a)==set('ABCD')
        if any(r['initial'] is None for r in a.values()):continue
        if max(r['initial'] for r in a.values())-min(r['initial'] for r in a.values())>=1e-10:continue
        A,B,C,D=(a[x]['gain'] for x in 'ABCD')
        for k,v in [('interaction',D-B-C+A),('D_minus_C',D-C),('D_minus_B',D-B),('B_minus_A',B-A),('C_minus_A',C-A)]:contrasts[k].append(v)
    stats={}
    for k,v in contrasts.items():
        v.sort();n=len(v);med=(v[(n-1)//2]+v[n//2])/2 if n else None
        avg=math.fsum(v)/n if n else None;var=math.fsum((x-avg)**2 for x in v)/(n-1) if n>1 else None
        rr=summary['contrasts'][k];assert rr['n']==n and close(med,rr['median']) and close(var,rr['sample_variance'])
        stats[k]=dict(n=n,median=med,sample_variance=var)
    gate=all(stats[k]['n']==2 and stats[k]['median']>0 for k in ('interaction','D_minus_C','D_minus_B'))
    assert gate==summary['numerical_gate']
    out=dict(status='PASS',plan_sha256=PLAN,summary_sha256=sha(R/'readout-v1/summary.json'),
        verifier_sha256=sha(Path(__file__)),valid_scores_recomputed=valid,trajectories=len(actual),
        checked_bindings=binding_count,prompt_chronology=checks,contrasts=stats,numerical_gate=gate,
        limitations='independent AUC pair algebra and effect arithmetic; uses same approved development labels; verifies transport not evidence causality, novel method or final-test benefit')
    with (R/'readout-v1/verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k!='prompt_chronology'},sort_keys=True))
if __name__=='__main__':main()
