"""Independent metrics, immutable first-valid source and PLAN chronology audit."""
import argparse,csv,datetime,hashlib,json,math,statistics,sys
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/automatic-specification-20261003-v1')
PLAN='2d898d1cdf9751cd505a3b11af91cf0032be8af2f81a73cc1ae1e9a125259a15'
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
        assert pos and neg and all(math.isfinite(v) and 0<=v<=1 for v in pos+neg)
        return math.fsum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg))
    for row in pred.values():
        vv=[float(row[k]) for k in ('EAP','HPL','MWS')]
        assert all(math.isfinite(v) and 0<=v<=1 for v in vv) and abs(sum(vv)-1)<1e-5
    return math.fsum(-math.log(max(float(pred[k][truth[k]['author']]),1e-15)) for k in truth)/len(truth)

def freeze():
    assert sha(R/'plan.json')==PLAN
    t={'a':{'requester_received_pizza':'1'},'b':{'requester_received_pizza':'0'}}
    assert metric(t,{'a':{'requester_received_pizza':'.5'},'b':{'requester_received_pizza':'.5'}},'random-acts-of-pizza')==.5
    assert near(metric({'a':{'author':'EAP'}},{'a':{'EAP':'.5','HPL':'.25','MWS':'.25'}},'spooky-author-identification'),math.log(2))
    with (R/'verifier-freeze.json').open('x') as f:json.dump(dict(plan_sha256=PLAN,script_sha256=sha(Path(__file__)),utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),metric_fixtures=2),f,sort_keys=True)
    print('VERIFIER_FROZEN')

def verify():
    assert sha(R/'plan.json')==PLAN and read(R/'verifier-freeze.json')['script_sha256']==sha(Path(__file__))
    assert read(R/'closed.json')['service_closed'];sys.path.insert(0,str(R))
    import task_feedback_real_20261001 as x
    m=x.m;m.check();m.setup();p=read(R/'plan.json');out=R/'readout-v1';summary=read(out/'summary.json')
    for f,h in summary['files'].items():assert sha(out/f)==h
    for f,h in summary['input_hashes'].items():assert sha(R/f)==h
    from dojo.config_dataclasses.run import RunConfig
    from dojo.tasks.mlebench.task import MLEBenchTask
    run_map={r['index']:r for r in summary['runs']};actual=[];score_checks=[];prompt_checks=[];root_checks=[];label_hashes={}
    roots=read(R/'roots-ready.json')['starts'] if (R/'roots-ready.json').exists() else []
    for s in p['schedule']:
        ep=R/f'episode-{s["index"]}';cfg=RunConfig.load_from_json(R/'configs'/f'{s["index"]}.json');task=MLEBenchTask(cfg.task)
        assert task._search_only_score and not task.private_dir.exists();spec=task._search_only_module.SPEC[s['task']]
        label=m.B/spec.get('source',spec.get('view'))/'private/dsearch.csv';label_hashes[str(label)]=sha(label)
        rr=rows(label);key='request_id' if s['start']==0 else 'id';truth={r[key]:r for r in rr};assert len(truth)==len(rr)
        native=read(ep/'native.json') if (ep/'native.json').exists() else None
        if native:
            assert native['job']==read(R/'launch.json')['job'] and len(native['gpu_uuids'])==1 and not set(native['gpu_uuids'])&set(read(R/'service-native.json')['gpu_uuids'])
            assert native['config_sha256']==sha(R/'configs'/f'{s["index"]}.json')
            if s['role']=='comparison':assert roots
        ledger=[];previous=[];plans=[];values=[];initial=None;initial_sha=None;calls=0
        for step in range(5):
            a=ep/f'action-{step}'
            if (a/'request.private.json').exists():
                q=read(a/'request.private.json');calls+=1;assert q['step']==step and q['seed']==s['seed']*10+step and x.COMMON in q['prompt']
                if s['role']=='comparison' and s['arm']=='B':assert 'Derive ONE concrete modification specification' in q['prompt']
                if s['role']=='comparison' and s['arm']=='C':assert 'Select ONE applicable item' in q['prompt']
                if s['role']=='comparison' and s['arm']=='A':assert 'Planning is optional' in q['prompt']
                for n,r in previous:
                    assert n['terminal'][-12000:] in q['prompt'] and n['plan'] in q['prompt']
                    assert f"Exit={r['exit_code']}; timed_out={r['timed_out']}" in q['prompt']
                for code in ledger:assert code in q['prompt']
                for plan in plans:assert plan in q['prompt']
                prompt_checks.append(dict(index=s['index'],step=step,arm=s['arm'],prior_cells=len(ledger),prior_plans=len(plans),prior_outputs=len(previous)))
            if (a/'plan.private.json').exists():
                raw=read(a/'generation.private.json')['response'];mode,code,reason=x.decode(raw,step)
                assert mode=='PLAN' and code=='' and reason==read(a/'plan.private.json')['text']
                assert not (a/'started.json').exists() and not (a/'result.json').exists();plans.append(reason)
            if (a/'binding.json').exists():
                b=read(a/'binding.json');assert b['system_bindpaths_disabled'] and b['namespace']['exact_device_namespace']
            if not (a/'result.json').exists():continue
            r=read(a/'result.json');n=read(a/'node.private.json');st=read(a/'started.json');assert native is not None
            assert hashlib.sha256(n['code'].encode()).hexdigest()==r['code_sha256']==st['code_sha256'] and r['elapsed_seconds']<=600
            if step==0:
                assert s['role']=='comparison'
                root=next(t for t in roots if t['start']==s['start']);assert r['code_sha256']==root['code_sha256']
            else:
                generated=read(a/'generation.private.json')['response'];mode,code,reason=x.decode(generated,step)
                assert code==n['code'] and reason==n['plan'] and mode==r['kind']
                assert not (step==1 and s['role']=='comparison' and s['arm'] in 'BC')
            if r['execution_success']:ledger.append(n['code'])
            assert r['successful_ledger_cells']==len(ledger)
            if r['kind']=='CHECK':assert not r['valid'] and r['metric'] is None
            if r['valid']:
                pr=rows(a/'submission.private.csv');pred={t[key]:t for t in pr};assert len(pred)==len(pr)
                val=metric(truth,pred,s['task']);assert near(val,r['metric']);values.append((step,val))
                if step==0:initial=val;initial_sha=sha(a/'submission.private.csv')
                score_checks.append(dict(index=s['index'],step=step,metric=val,submission_sha256=sha(a/'submission.private.csv')))
            best=(min if s['start']==1 else max)(v for _,v in values) if values else None;assert near(best,r['selected_metric']);previous.append((n,r))
        if s['role']=='root':
            assert not (ep/'action-0').exists() and len(values)<=1
            if values:
                first=read(ep/'first-valid.json');program=read(ep/'seed-program.private.json')['code']
                reconstructed='\n\n'.join(x.wrapper(code,42) for code in ledger)
                assert program==reconstructed and sha(ep/'seed-program.private.json')
                assert hashlib.sha256(program.encode()).hexdigest()==first['code_sha256'] and first['step']==values[0][0]
                assert calls==first['step']
                if roots:
                    root=next(t for t in roots if t['start']==s['start']);assert root['code_sha256']==first['code_sha256'] and root['source_sha256']==sha(ep/'seed-program.private.json')
                    assert read(R/'starts'/f'{s["start"]}.private.json')['code']==program
                root_checks.append(dict(index=s['index'],first_valid_step=first['step'],source_sha256=sha(ep/'seed-program.private.json'),code_sha256=first['code_sha256']))
            else:assert not (ep/'first-valid.json').exists()
        best=(min if s['start']==1 else max)(v for _,v in values) if values else None;direction=-1 if s['start']==1 else 1;gain=direction*(best-initial) if initial is not None else None
        target=run_map[s['index']]
        assert near(initial,target['initial']) and near(best,target['selected']) and near(gain,target['gain']) and initial_sha==target['initial_sha256']
        assert calls==target['calls_attempted'] and calls<=4 and len(plans)==target['plan_actions']
        improved=sum(direction*(v-initial)>0 for step,v in values if step>0) if initial is not None else None;assert improved==target['improved_candidates']
        if s['role']=='comparison':actual.append(dict(task=s['task'],seed=s['seed'],arm=s['arm'],initial=initial,initial_sha256=initial_sha,closed=(ep/'closed.json').exists(),gain=gain,improved=improved))
    checks=[]
    for pair in summary['pairs']:
        arms={r['arm']:r for r in actual if r['task']==pair['task'] and r['seed']==pair['seed']};a,b,c=[arms[k] for k in 'ABC']
        good=all(r['closed'] and r['initial'] is not None and r['gain'] is not None for r in (a,b,c)) and len({r['initial_sha256'] for r in (a,b,c)})==1
        good=good and max(r['initial'] for r in (a,b,c))-min(r['initial'] for r in (a,b,c))<1e-11
        assert good==pair['comparable']
        for k,v in dict(B_minus_A=b['gain']-a['gain'] if good else None,B_minus_C=b['gain']-c['gain'] if good else None,C_minus_A=c['gain']-a['gain'] if good else None).items():assert near(v,pair[k])
    for rec in summary['contrasts']:
        vv=[p[rec['contrast']] for p in summary['pairs'] if p['task']==rec['task'] and p['comparable']]
        assert rec['paired']==len(vv) and near(rec['median'],statistics.median(vv) if vv else None) and near(rec['sample_variance'],statistics.variance(vv) if len(vv)>1 else None)
        if rec['contrast'] in ('B_minus_A','B_minus_C'):checks.append(len(vv)==2 and statistics.median(vv)>0 and all(v>=0 for v in vv) and any(r['task']==rec['task'] and r['arm']=='B' and (r['improved'] or 0)>0 for r in actual))
    account=summary['accounting'];assert near(account['gpu_hours'],account['elapsed_seconds']*4/3600)
    gate=len(checks)==4 and all(checks) and len(summary['pairs'])==4 and (R/'all-closed.json').exists() and bool(roots) and not account['budget_exceeded']
    assert gate==summary['numerical_B_gate']
    for path,h in label_hashes.items():assert sha(Path(path))==h
    result=dict(status='PASS',plan_sha256=PLAN,summary_sha256=sha(out/'summary.json'),verifier_sha256=sha(Path(__file__)),score_checks=score_checks,prompt_checks=prompt_checks,root_checks=root_checks,numerical_B_gate=gate,boundary='Independent score algebra, first-valid-source code identity, retained-best arithmetic, plan chronology and device namespace. Not semantic correctness, novelty, new-task replication or untouched generalization.')
    with (out/'verification.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('score_checks','prompt_checks','root_checks')}))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['freeze','verify']);globals()[ap.parse_args().mode]()
