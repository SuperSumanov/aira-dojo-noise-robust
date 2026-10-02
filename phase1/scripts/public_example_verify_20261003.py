"""Independent score algebra and observation/seed/retained-state verification."""
import csv,hashlib,json,math,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/public-example-feedback-20261003-v1')
PLAN='40e6bc3301c1db52fa09a794577c0b5dc95533302b0e460a044942a6485c5376'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def close(a,b):return (a is None and b is None) or (a is not None and b is not None and math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-11))
def metric(truth,pred,task):
    assert set(truth)==set(pred)
    if task=='random-acts-of-pizza':
        p={k:float(v['requester_received_pizza']) for k,v in pred.items()};assert all(math.isfinite(v) for v in p.values())
        pos=[v for k,v in p.items() if int(truth[k]['requester_received_pizza'])==1];neg=[v for k,v in p.items() if int(truth[k]['requester_received_pizza'])==0]
        assert pos and neg
        return math.fsum(1 if a>b else .5 if a==b else 0 for a in pos for b in neg)/(len(pos)*len(neg))
    assert task=='spooky-author-identification';loss=[]
    for k,v in truth.items():
        p={c:float(pred[k][c]) for c in ('EAP','HPL','MWS')}
        assert all(math.isfinite(x) and 0<=x<=1 for x in p.values()) and abs(math.fsum(p.values())-1)<1e-6
        loss.append(-math.log(max(p[v['author']],1e-15)))
    return math.fsum(loss)/len(loss)
def main():
    assert sha(R/'plan.json')==PLAN and read(R/'closed.json')['service_closed']
    sys.path.insert(0,str(R));import task_feedback_real_20261001 as d
    m=d.m;p=m.check();m.setup()
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    summary=read(R/'readout-v1/summary.json');assert summary['plan_sha256']==PLAN
    for f,h in summary['files'].items():assert sha(R/'readout-v1'/f)==h
    for f,h in summary['input_hashes'].items():assert sha(R/f)==h
    sr={r['index']:r for r in summary['runs']};actual=[];verified=[];prompt_checks=[]
    job=read(R/'launch.json')['job'];service=read(R/'service-native.json');assert service['job']==job
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}';ledger=[];previous=[];values=[];initial=None;calls=0;pack=None;native=None
        if (ep/'native.json').exists():
            native=read(ep/'native.json');assert native['job']==job and len(native['gpu_uuids'])==1 and not set(native['gpu_uuids'])&set(service['gpu_uuids'])
            assert native['config_sha256']==sha(R/'configs'/f'{s["index"]}.json')
        cfg=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');task=MLEBenchTask(cfg.task)
        assert task._search_only_score and not task.private_dir.exists();spec=task._search_only_module.SPEC[s['task']]
        data=rows(m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv');key='request_id' if s['start']==0 else 'id'
        truth={row[key]:row for row in data};assert len(truth)==len(data)
        for step in range(7):
            a=ep/f'action-{step}'
            if (a/'request.private.json').exists():
                q=read(a/'request.private.json');calls+=1;assert q['step']==step and q['seed']==s['seed']*10+step
                for prev,pr,pn in previous:
                    assert pn['terminal'][-18000:] in q['prompt'] and pn['plan'] in q['prompt']
                    assert f"Exit={pr['exit_code']}; timed_out={pr['timed_out']}" in q['prompt']
                for c in ledger:assert c in q['prompt']
                if pack:
                    assert json.dumps(pack['shown'],sort_keys=True,ensure_ascii=False) in q['prompt']
                    assert 'mean_selected_loss' not in q['prompt']
                prompt_checks.append(dict(index=s['index'],step=step,ledger_cells=len(ledger),previous_outputs=len(previous),packet_present=pack is not None))
            if (a/'binding.json').exists():
                binding=read(a/'binding.json');assert binding['system_bindpaths_disabled'] and binding['namespace']['exact_device_namespace']
            if not (a/'result.json').exists():continue
            r=read(a/'result.json');n=read(a/'node.private.json');st=read(a/'started.json');assert native is not None
            assert hashlib.sha256(n['code'].encode()).hexdigest()==r['code_sha256']==st['code_sha256'] and r['elapsed_seconds']<=900
            executed=n['code']+d.evidence_code(s) if step==0 else n['code']
            assert read(a/'executed.json')['code_sha256']==hashlib.sha256(executed.encode()).hexdigest()
            if step==0:
                assert r['code_sha256']==p['starts'][s['start']]['code_sha256']
                if r['execution_success']:
                    pack=read(a/'public-packet.private.json');meta=pack['metadata'];shown=pack['shown']
                    assert meta['policy']==s['arm'] and meta['seed']==s['seed'] and len(shown['examples'])==12
                    assert [x['row_index'] for x in shown['examples']]==meta['selected_indices'] and len(set(meta['selected_indices']))==12
                    assert hashlib.sha256(json.dumps(shown,sort_keys=True,ensure_ascii=False).encode()).hexdigest()==meta['shown_sha256']
                    counts={name:sum(x['true_class']==name for x in shown['examples']) for name in meta['class_counts']}
                    assert set(counts.values())=={12//len(counts)}
            if r['kind']=='CHECK':assert not r['valid'] and r['metric'] is None
            if r['execution_success']:ledger.append(n['code'])
            assert len(ledger)==r['successful_ledger_cells']
            if r['valid']:
                assert r['kind']=='SOLUTION' and r['exit_code']==0 and not r['timed_out']
                predrows=rows(a/'submission.private.csv');pred={row[key]:row for row in predrows};assert len(pred)==len(predrows)
                v=metric(truth,pred,s['task']);assert close(v,r['metric']);values.append(v)
                if step==0:initial=v
            best=(min if s['start']==1 else max)(values) if values else None
            assert close(best,r['selected_metric']);previous.append((step,r,n));verified.append(dict(index=s['index'],step=step,valid=r['valid']))
        best=(min if s['start']==1 else max)(values) if values else None
        gain=(-1 if s['start']==1 else 1)*(best-initial) if initial is not None else None
        for k,v in [('initial',initial),('selected',best),('gain',gain)]:assert close(v,sr[s['index']][k])
        assert calls==sr[s['index']]['calls_attempted'] and calls<=6
        actual.append(dict(task=s['task'],seed=s['seed'],arm=s['arm'],initial=initial,gain=gain,closed=(ep/'closed.json').exists(),
                           diagnostic=pack['metadata']['predictions_sha256'] if pack else None,labels=pack['metadata']['labels_sha256'] if pack else None,
                           improved=sum((1 if s['start']==0 else -1)*(v-initial)>1e-12 for v in values[1:]) if initial is not None else 0))
    stats=[];pairs=[]
    for task in sorted({r['task'] for r in actual}):
        delta=[]
        for seed in sorted({r['seed'] for r in actual if r['task']==task}):
            arms={r['arm']:r for r in actual if r['seed']==seed};a,b=arms['uniform'],arms['contrast']
            match=a['initial'] is not None and b['initial'] is not None and abs(a['initial']-b['initial'])<1e-10 and a['diagnostic'] is not None and a['diagnostic']==b['diagnostic'] and a['labels']==b['labels'] and a['closed'] and b['closed']
            expected=next(r for r in summary['pairs'] if r['seed']==seed);assert expected['comparable']==match
            if match:delta.append(b['gain']-a['gain']);assert close(delta[-1],expected['contrast_minus_uniform'])
            pairs.append(dict(task=task,seed=seed,comparable=match))
        ordered=sorted(delta);n=len(delta);med=(ordered[(n-1)//2]+ordered[n//2])/2 if n else None
        mean=math.fsum(delta)/n if n else None;var=math.fsum((x-mean)**2 for x in delta)/(n-1) if n>1 else None
        r=next(t for t in summary['tasks'] if t['task']==task)
        assert r['paired']==n and close(med,r['median_delta']) and close(var,r['sample_variance'])
        assert r['uniform_wins']==sum(x<0 for x in delta) and r['contrast_wins']==sum(x>0 for x in delta)
        improved=sum(a['improved'] for a in actual if a['task']==task);assert r['improved_candidates']==improved
        stats.append(dict(task=task,paired=n,median_delta=med,sample_variance=var,uniform_wins=sum(x<0 for x in delta),improved_candidates=improved))
    gate=(R/'all-closed.json').exists() and all(t['paired']==2 and t['median_delta']>0 and t['uniform_wins']==0 and t['improved_candidates']>0 for t in stats)
    assert gate==summary['numerical_gate']
    out=dict(status='PASS',plan_sha256=PLAN,summary_sha256=sha(R/'readout-v1/summary.json'),verifier_sha256=sha(Path(__file__)),
        valid_scores_recomputed=sum(v['valid'] for v in verified),actions=len(verified),prompt_chronology=prompt_checks,paired_checks=pairs,tasks=stats,numerical_gate=gate,
        scope='independent pair-count AUC/direct log loss and arithmetic; verifies packet/code/hash/transport but does not rerun all public OOF arrays, establish evidence causality, novelty or untouched-test benefit')
    with (R/'readout-v1/verification.json').open('x') as f:json.dump(out,f,sort_keys=True,indent=2)
    print(json.dumps({k:v for k,v in out.items() if k not in ('prompt_chronology','paired_checks')},sort_keys=True))
if __name__=='__main__':main()
