"""Independent arithmetic, direct metric algebra, and observation chronology."""
import csv,hashlib,json,math,statistics,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/opportunity-information-20261003-v2');PLAN='6b91aba97ee53f6da2335064f1dbe4277020b8744fd95a3575e4c99329936d2f'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def near(a,b):return a is None and b is None or a is not None and b is not None and math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-11)
def metric(truth,pred,task):
    assert set(truth)==set(pred)
    if task=='random-acts-of-pizza':
        pos=[float(pred[k]['requester_received_pizza']) for k in truth if int(truth[k]['requester_received_pizza'])==1]
        neg=[float(pred[k]['requester_received_pizza']) for k in truth if int(truth[k]['requester_received_pizza'])==0]
        assert pos and neg
        return math.fsum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))
    return math.fsum(-math.log(max(float(pred[k][truth[k]['author']]),1e-15)) for k in truth)/len(truth)
def main():
    assert sha(R/'plan.json')==PLAN and read(R/'closed.json')['service_closed'];sys.path.insert(0,str(R))
    import task_feedback_real_20261001 as x
    m=x.m;m.check();m.setup();p=read(R/'plan.json');out=R/'readout-v1';summary=read(out/'summary.json')
    for f,h in summary['files'].items():assert sha(out/f)==h
    for f,h in summary['input_hashes'].items():assert sha(R/f)==h
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    run_map={r['index']:r for r in summary['runs']};actual=[];score_checks=[];prompt_checks=[];label_hashes={}
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}';cfg=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');task=MLEBenchTask(cfg.task)
        assert task._search_only_score and not task.private_dir.exists();spec=task._search_only_module.SPEC[s['task']]
        label=m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv';label_hashes[str(label)]=sha(label)
        rr=rows(label);key='request_id' if s['start']==0 else 'id';truth={r[key]:r for r in rr};assert len(truth)==len(rr)
        native=read(ep/'native.json') if (ep/'native.json').exists() else None
        if native:
            assert native['job']==read(R/'launch.json')['job'] and len(native['gpu_uuids'])==1 and not set(native['gpu_uuids'])&set(read(R/'service-native.json')['gpu_uuids'])
            assert native['config_sha256']==sha(R/'configs'/f'{s["index"]}.json')
        ledger=[];previous=[];values=[];initial=None;initial_sha=None;calls=0
        for step in range(5):
            a=ep/f'action-{step}'
            if (a/'request.private.json').exists():
                q=read(a/'request.private.json');calls+=1;assert q['step']==step and q['seed']==s['seed']*10+step
                assert (x.FACTS[s['start']] in q['prompt'])==(s['arm']=='B') and (x.SPECS[s['start']] in q['prompt'])==(s['arm']=='C')
                for n,r in previous:
                    assert n['terminal'][-12000:] in q['prompt'] and n['plan'] in q['prompt']
                    assert f"Exit={r['exit_code']}; timed_out={r['timed_out']}" in q['prompt']
                for c in ledger:assert c in q['prompt']
                prompt_checks.append(dict(index=s['index'],step=step,arm=s['arm'],prior_cells=len(ledger),prior_outputs=len(previous)))
            if (a/'binding.json').exists():
                b=read(a/'binding.json');assert b['system_bindpaths_disabled'] and b['namespace']['exact_device_namespace']
            if not (a/'result.json').exists():continue
            r=read(a/'result.json');n=read(a/'node.private.json');st=read(a/'started.json');assert native is not None
            assert hashlib.sha256(n['code'].encode()).hexdigest()==r['code_sha256']==st['code_sha256'] and r['elapsed_seconds']<=600
            if step==0:assert r['code_sha256']==p['starts'][s['start']]['code_sha256']
            else:
                generated=read(a/'generation.private.json')['response'];mode,code,reason=x.decode(generated,step);assert code==n['code'] and reason==n['plan'] and mode==r['kind']
            if r['execution_success']:ledger.append(n['code'])
            assert r['successful_ledger_cells']==len(ledger)
            if r['kind']=='CHECK':assert not r['valid'] and r['metric'] is None
            if r['valid']:
                pr=rows(a/'submission.private.csv');pred={t[key]:t for t in pr};assert len(pred)==len(pr)
                value=metric(truth,pred,s['task']);assert near(value,r['metric']);values.append((step,value))
                if step==0:initial=value;initial_sha=sha(a/'submission.private.csv')
                score_checks.append(dict(index=s['index'],step=step,metric=value,submission_sha256=sha(a/'submission.private.csv')))
            best=(min if s['start']==1 else max)(v for _,v in values) if values else None;assert near(best,r['selected_metric']);previous.append((n,r))
        best=(min if s['start']==1 else max)(v for _,v in values) if values else None;direction=-1 if s['start']==1 else 1;gain=direction*(best-initial) if initial is not None else None
        target=run_map[s['index']]
        assert near(initial,target['initial']) and near(best,target['selected']) and near(gain,target['gain']) and initial_sha==target['initial_sha256']
        assert calls==target['calls_attempted'] and calls<=4
        improved=sum(direction*(v-initial)>1e-12 for step,v in values if step>0) if initial is not None else None;assert improved==target['improved_candidates']
        actual.append(dict(task=s['task'],seed=s['seed'],arm=s['arm'],initial=initial,initial_sha256=initial_sha,closed=(ep/'closed.json').exists(),gain=gain,improved=improved))
    pairs=[];stats=[]
    for task in sorted({r['task'] for r in actual}):
        for seed in sorted({r['seed'] for r in actual if r['task']==task}):
            arms={r['arm']:r for r in actual if r['task']==task and r['seed']==seed};a,b,c=[arms[k] for k in 'ABC']
            comparable=all(r['closed'] and r['initial'] is not None for r in (a,b,c)) and len({r['initial_sha256'] for r in (a,b,c)})==1
            expected=next(p for p in summary['pairs'] if p['task']==task and p['seed']==seed);assert comparable==expected['comparable']
            vals=dict(B_minus_A=b['gain']-a['gain'] if comparable else None,C_minus_A=c['gain']-a['gain'] if comparable else None,C_minus_B=c['gain']-b['gain'] if comparable else None)
            for k,v in vals.items():assert near(v,expected[k])
            pairs.append(dict(task=task,seed=seed,comparable=comparable,**vals))
        for contrast in ('B_minus_A','C_minus_A','C_minus_B'):
            vals=[r[contrast] for r in pairs if r['task']==task and r['comparable']];med=statistics.median(vals) if vals else None;var=statistics.variance(vals) if len(vals)>1 else None
            expected=next(t for t in summary['contrasts'] if t['task']==task and t['contrast']==contrast)
            assert near(med,expected['median']) and near(var,expected['sample_variance'])
            stats.append(dict(task=task,contrast=contrast,paired=len(vals),median=med,sample_variance=var,negative=sum(v< -1e-12 for v in vals)))
    gate=(R/'all-closed.json').exists() and all(t['paired']==2 and t['median']>0 and t['negative']==0 and any(r['arm']=='B' and r['task']==t['task'] and (r['improved'] or 0)>0 for r in actual) for t in stats if t['contrast']=='B_minus_A')
    assert gate==summary['numerical_B_gate']
    for path,h in label_hashes.items():assert sha(Path(path))==h
    result=dict(status='PASS',plan_sha256=PLAN,summary_sha256=sha(out/'summary.json'),verifier_sha256=sha(Path(__file__)),score_checks=score_checks,prompt_checks=prompt_checks,contrasts=stats,numerical_B_gate=gate,
        boundary='Independent score algebra, retained-best arithmetic, prompt chronology and physical GPU namespace. Does not certify semantic target implementation, information-causal attribution, new-method superiority or untouched generalization.')
    with (out/'verification.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('score_checks','prompt_checks')}))
if __name__=='__main__':main()
