"""Frozen full-denominator readout, no success metric based on generation speed."""
import argparse,csv,hashlib,json,math,statistics,sys
from pathlib import Path
ARMS=('medium','fast_code','feedback_think');ORDER=ARMS+tuple(reversed(ARMS))
TASKS=('aerial-cactus-identification','denoising-dirty-documents');SIGN={TASKS[0]:1,TASKS[1]:-1}
def read(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(s) for s in Path(p).read_text().splitlines() if s]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False)
def quality(scores):
    contrasts=[]
    for rep in range(2):
        blocks={ORDER[b]:b for b in range(rep*3,rep*3+3)}
        for task in TASKS:
            for ref in ARMS[:2]:
                a,b=scores[blocks[ARMS[2]],task],scores[blocks[ref],task]
                contrasts.append(dict(repeat=rep,task=task,reference=ref,method_best=a,reference_best=b,oriented_delta=SIGN[task]*(a-b)))
    return contrasts,all(x['oriented_delta']>=(.001 if x['task']==TASKS[1] else -1e-12) for x in contrasts)

def analyze(root,out,gpu_seconds):
    root=Path(root);p=read(root/'plan.json');cl=read(root/'closed.json')
    assert p['planned']==48 and p['allocation_seconds']==7800 and p['prior_failures']==[]
    assert 0<gpu_seconds<=46800 and p['run_seconds']==1020 and p['slot_seconds']==1180
    assert all(sha(root/n)==h for n,h in p['files'].items())
    assert all(sha(root/n)==h for n,h in p['input_files'].items())
    sys.path.insert(0,str(root))
    from image_dev_data_20261011 import score_at
    from live_readout import timely_returns,ground_scores,queue_verify
    from live_identity import cores
    from feedback_parent_readout_20261012 import audit
    from feedback_effort_policy_20261012 import thinking
    spec=read(root/'dev-views/spec.json');warm=read(root/'warm-receipt.json');rows=[];recomputed=0;efforts=[]
    for s in p['schedule']:
        ep=root/f"episode-{s['index']}";f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        closure=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        cs=[read(x) for x in ep.glob('candidate-*.json') if '.private.' not in x.name];timely=timely_returns(cs,1020);receipts=[]
        for x in ep.glob('scored-*.json'):
            receipt=read(x)['receipt'];receipts.append(receipt)
            actual=score_at(root,spec,s['task'],ep/(x.stem+'.private.csv'));metric=spec[s['task']]['metric_name']
            assert actual['submission_sha256']==receipt['submission_sha256'] and abs(actual[metric]-receipt[metric])<=1e-12
            recomputed+=1
        assert ground_scores(dict(f,native_selected_valid=False),timely,receipts)
        eligible=[r['score'] for r in timely if r.get('valid') is True and r.get('exit_code')==0 and not r.get('timed_out') and type(r.get('score')) in (int,float) and math.isfinite(r['score'])]
        complete=closure.get('returncode')==0 and closure.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted')
        best=max([warm[s['task']]['score']]+eligible,key=lambda x:SIGN[s['task']]*x) if complete else None
        rows.append(dict(s,source_commit=p['source_commit'],run_seconds=1020,pool_seconds=1180,score=best,
            started=(ep/'deadline.json').exists(),complete=complete,cleanup=closure.get('cleanup_verified') is True,
            candidate_returns=len(timely),valid_returns=len(eligible)))
        if (ep/'effort.jsonl').exists():
            for e in lines(ep/'effort.jsonl'):
                assert e['arm']==s['arm'] and e['enable_thinking'] is thinking(s['arm'],e['role'])
                assert e['effort']==('medium' if e['enable_thinking'] else 'none')
                efforts.append(dict(index=s['index'],task=s['task'],**e))
    # Incomplete batches remain incomplete; no fabricated warm-start scores.
    out=Path(out);out.mkdir();write(out/'runs.json',rows);write(out/'effort.json',efforts)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    if not all(r['complete'] for r in rows):
        result=dict(assigned=48,started=sum(r['started'] for r in rows),complete=sum(r['complete'] for r in rows),
            predeclared_success_gate_met=False,incomplete=True,scores_recomputed=recomputed,gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
            plan_sha256=sha(root/'plan.json'),source_commit=p['source_commit'],no_automatic_expansion=True)
        write(out/'summary.json',result);print(json.dumps(result));return
    identities=[];budgets=[];cpu=[];policies=[]
    for b in range(6):
        bd=root/f'block-{b}';slot=read(bd/'budget-slot.json');steps=read(bd/'steps.json')
        budgets.append(slot['reserved_seconds']==1180 and 1180<=slot['actual_seconds']<=1182 and steps['returncodes']==[0]*4)
        assert all(queue_verify(lines(root/f'queue-{b}-{lane}/events.jsonl'),1)['complete'] for lane in range(4))
        policies.append(dict(block=b,arm=ORDER[b],**audit(lines(root/f'generation-{b}/events.jsonl'),'greedy')))
        st=read(root/f'generation-{b}/state.json');assert not st['pending'] and not st['waiting'] and not st['active']
        service=read(bd/'service-native.json');lanes=[read(bd/f'lane-{i}-native.json') for i in range(4)]
        devices=[x['gpu_uuid'] for x in lanes];sv=service['gpu_uuids'];sets=[cores(x['cpu_topology']) for x in lanes]+[cores(service['cpu_topology'])]
        valid=len(set(devices))==4 and len(set(sv))==2 and not set(devices)&set(sv) and all(len(x)==4 for x in sets[:4]) and len(sets[-1])==8 and all(not sets[i]&sets[j] for i in range(5) for j in range(i))
        identities.append(dict(block=b,lanes=devices,service=sv,valid=valid))
        for lane in range(4):
            a,c=(read(root/f'episode-{b*8+lane*2+k}/cpu-partition.json') for k in (0,1));ac,cc=cores(a['worker_topology']),cores(c['worker_topology'])
            cpu.append(len(ac)==len(cc)==2 and not ac&cc and ac|cc==cores(a['parent_topology'])==cores(c['parent_topology']))
    cleanup=read(root/'block-0/service-cleanup.json')
    structure=all(budgets) and all(cpu) and cl['error'] is None and cleanup['gpu_clean'] and all(i['valid'] and i['lanes']==identities[0]['lanes'] and set(i['service'])==set(identities[0]['service']) for i in identities)
    scores={(b,t):max([r['score'] for r in rows if (r['block'],r['task'])==(b,t)],key=lambda x:SIGN[t]*x) for b in range(6) for t in TASKS}
    contrasts,passed=quality(scores)
    mechanism=all(any(e['index']//8==b and e['role']=='improve' and not e['enable_thinking'] and e['success'] for e in efforts)
                  and any(e['index']//8==b and e['role']=='debug' and e['enable_thinking'] and e['success'] for e in efforts) for b in (2,3))
    result=dict(assigned=48,complete=48,source_commit=p['source_commit'],plan_sha256=sha(root/'plan.json'),readout_sha256=sha(__file__),
        scores_recomputed=recomputed,contrasts=contrasts,quality_gate=passed,structural_gate=bool(structure),mechanism_gate=mechanism,
        predeclared_success_gate_met=bool(passed and structure and mechanism),gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
        cpu_pairs_passed=sum(cpu),no_automatic_expansion=True,policies=policies,
        by_arm={a:{t:dict(median=statistics.median([r['score'] for r in rows if (r['arm'],r['task'])==(a,t)]),sample_sd=statistics.stdev([r['score'] for r in rows if (r['arm'],r['task'])==(a,t)])) for t in TASKS} for a in ARMS},limitation=p['limitation'])
    write(out/'identity.json',identities);write(out/'summary.json',result);print(json.dumps(result,allow_nan=False))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('out');ap.add_argument('--gpu-seconds',type=int,required=True)
    a=ap.parse_args();analyze(a.root,a.out,a.gpu_seconds)
