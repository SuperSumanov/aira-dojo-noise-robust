"""Frozen32 assigned endpoints, two reverse-order pool repeats, no pooled rescue."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

TASKS=('aerial-cactus-identification','denoising-dirty-documents')
SIGN={TASKS[0]:1,TASKS[1]:-1};ORDER=('shared','colocated','colocated','shared')
RUN,SLOT,CAP=1020,1180,6000
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def lines(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x] if Path(p).exists() else []
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,sort_keys=True,indent=2,allow_nan=False)


def quality(rows):
    by=[]
    for b,mode in enumerate(ORDER):
        for task in TASKS:
            v=[r['score'] for r in rows if r['block']==b and r['task']==task]
            assert len(v)==4 and all(type(x) in (float,int) and math.isfinite(x) for x in v)
            by.append(dict(block=b,repeat=b//2,pool_mode=mode,task=task,best=max(v,key=lambda x:SIGN[task]*x),median=statistics.median(v),sample_sd=statistics.stdev(v),n=4))
    contrasts=[]
    for rep in range(2):
        for task in TASKS:
            d={r['pool_mode']:r for r in by if r['repeat']==rep and r['task']==task}
            contrasts.append(dict(repeat=rep,task=task,baseline_best=d['shared']['best'],colocated_best=d['colocated']['best'],
                oriented_delta=SIGN[task]*(d['colocated']['best']-d['shared']['best']),
                median_delta=SIGN[task]*(d['colocated']['median']-d['shared']['median'])))
    return by,contrasts,all(r['oriented_delta']>=(.001 if r['task']==TASKS[1] else -1e-12) for r in contrasts)


def verify_queue(events,mode):
    assert mode in ('shared','colocated')
    cap=2 if mode=='colocated' else 1
    waiting=[];busy={};seen=set();requests={};last=-math.inf
    migrations=co_admissions=peak=0;waits=[]
    for e in events:
        k,t=e['key'],e['time']
        assert math.isfinite(t) and t>=last;last=t
        if e['event']=='queued':
            assert k not in seen;seen.add(k);waiting.append(k)
            requests[k]=dict(home=e['home'],time=t)
        elif e['event']=='admitted':
            d=e['device'];assert k in waiting and waiting[0]==k
            counts=[sum(v==i for v in busy.values()) for i in range(4)]
            eligible=[i for i in range(4) if counts[i]<cap]
            assert eligible and d==min(eligible,key=lambda i:(counts[i],i))
            co_admissions+=counts[d]>0;peak=max(peak,counts[d]+1)
            waiting.remove(k);busy[k]=d;waits.append(t-requests[k]['time'])
            migrations+=d!=requests[k]['home']
        elif e['event']=='released':
            assert busy.pop(k)==e['device']
        elif e['event']=='queue_cancelled':
            waiting.remove(k)
        else:raise ValueError('unknown queue event')
        assert e['active']==len(busy) and e['queued']==len(waiting)
    assert not busy and not waiting
    return dict(admissions=len(waits),migrations=migrations,co_admissions=co_admissions,
        peak_device_leases=peak,wait_total=sum(waits),
        wait_median=statistics.median(waits) if waits else None)


def analyze(root,out,gpu_seconds):
    root,out=Path(root),Path(out);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert p['planned']==32 and p['allocation_seconds']==CAP and p['prior_failures']==[]
    assert 0<gpu_seconds<=36000 and p['run_seconds']==RUN and p['slot_seconds']==SLOT
    assert all(sha(root/n)==h for n,h in p['files'].items())
    assert all(sha(root/n)==h for n,h in p['input_files'].items())
    assert sha(root/'warm.private.json')==p['common_start_sha256'] and sha(root/'warm-receipt.json')==p['common_start_receipt_sha256']
    sys.path.insert(0,str(root))
    from image_dev_data_20261011 import score_at
    from live_readout import timely_returns,ground_scores
    from live_identity import cores
    from weight_confirmation_readout_20261014 import runtime_inputs
    from feedback_parent_readout_20261012 import audit
    spec,warm=read(root/'dev-views/spec.json'),read(root/'warm-receipt.json')
    rows=[];recomputed=0;calls=[]
    for s in p['schedule']:
        ep=root/f"episode-{s['index']}"
        f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        cl=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        candidates=[read(x) for x in ep.glob('candidate-*.json') if '.private.' not in x.name]
        timely=timely_returns(candidates,RUN);receipts=[]
        for x in ep.glob('scored-*.json'):
            rec=read(x)['receipt'];receipts.append(rec)
            actual=score_at(root,spec,s['task'],ep/(x.stem+'.private.csv'));metric=spec[s['task']]['metric_name']
            assert actual['submission_sha256']==rec['submission_sha256'] and abs(actual[metric]-rec[metric])<=1e-12
            recomputed+=1
        assert ground_scores(dict(f,native_selected_valid=False),timely,receipts)
        eligible=[r['score'] for r in timely if r.get('valid') is True and r.get('exit_code')==0 and not r.get('timed_out') and type(r.get('score')) in (int,float) and math.isfinite(r['score'])]
        complete=cl.get('returncode')==0 and cl.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted')
        initial=warm[s['task']]['score']
        rows.append(dict(s,source_commit=p['source_commit'],run_seconds=RUN,pool_seconds=SLOT,
            score=max([initial]+eligible,key=lambda x:SIGN[s['task']]*x) if complete else None,
            initial_score=initial,native_selected_score=f.get('native_selected_score'),
            started=(ep/'deadline.json').exists(),complete=complete,cleanup=cl.get('cleanup_verified') is True,
            candidate_returns=len(timely),valid_returns=len(eligible)))
        for e in lines(ep/'effort.jsonl'):
            expected='medium' if e['role']=='analyze' else 'none'
            assert e['arm']=='old_fast' and e['effort']==expected and e['enable_thinking'] is (expected!='none')
            assert e['model_id']=='qwen3.8-27b' and e['output_cap']==(8192 if e['role']=='analyze' else 32768)
            assert e['request_cap']==(600 if e['role']=='analyze' else 1500)
            calls.append(dict(index=s['index'],**e))
    out.mkdir();write(out/'runs.json',rows);write(out/'effort.json',calls)
    with (out/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=dict(assigned=32,complete=sum(r['complete'] for r in rows),started=sum(r['started'] for r in rows),
        gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,scores_recomputed=recomputed,
        plan_sha256=sha(root/'plan.json'),source_commit=p['source_commit'],reader_sha256=sha(__file__),
        quality_gate=False,predeclared_success_gate_met=False,limitation=p['limitation'])
    if not all(r['complete'] for r in rows):
        result['incomplete']=True;write(out/'summary.json',result);print(json.dumps(result));return
    inputs=runtime_inputs(root,p,rows);write(out/'input-checks.json',inputs)
    inputs_ok=all(x['passed'] for x in inputs)
    qualification=read(root/'dispatch-qualification.json')
    assert qualification['passed'] and len(qualification['rows'])==4
    identities=[];queues=[];bindings=[];partitions=[]
    allcpu=[]
    for b in range(4):
        bd=root/f'block-{b}';slot=read(bd/'budget-slot.json');ec=read(bd/'execution-closed.json')
        assert slot['reserved_seconds']==SLOT and SLOT<=slot['actual_seconds']<=SLOT+2
        assert read(bd/'steps.json')['returncodes']==[0] and ec['gpu_clean'] and not ec['telemetry_errors']
        events=lines(root/f'pool-{b}/events.jsonl');queues.append(dict(block=b,pool_mode=ORDER[b],**verify_queue(events,ORDER[b])))
        write(out/f'queue-{b}.json',events)
        execid,service=read(bd/'execution-native.json'),read(bd/'service-native.json')
        assert len(set(execid['gpu_uuids']))==4 and len(set(service['gpu_uuids']))==2 and not set(execid['gpu_uuids'])&set(service['gpu_uuids'])
        assert len(cores(execid['cpu_topology']))==16 and len(cores(service['cpu_topology']))==8 and not cores(execid['cpu_topology'])&cores(service['cpu_topology'])
        partitions=[]
        for s in p['schedule']:
            if s['block']!=b:continue
            ep=root/f"episode-{s['index']}";cp=read(ep/'cpu-partition.json')
            assert cp['chosen']==execid['cpu_slots'][s['slot']] and len(cores(cp['worker_topology']))==2
            partitions.append(set(cp['chosen']))
            for path in ep.glob('binding-*.json'):
                r=read(path);assert r['gpu_uuid']==execid['gpu_uuids'][r['device']] and r['namespace']['exact_device_namespace'] and r['system_bindpaths_disabled']
                assert any(e['event']=='admitted' and e['key']==r['key'] and e['device']==r['device'] for e in events)
                assert 0<=r['device']<4
                bindings.append(dict(index=s['index'],key=r['key'],device=r['device'],gpu_uuid=r['gpu_uuid']))
        assert len(partitions)==8 and len(set.union(*partitions))==16 and all(not partitions[i]&partitions[j] for i in range(8) for j in range(i))
        allcpu.append(execid['cpu_slots']);identities.append(dict(block=b,execution=execid['gpu_uuids'],service=service['gpu_uuids']))
        audit(lines(root/f'generation-{b}/events.jsonl'),'greedy')
        gs=read(root/f'generation-{b}/state.json');assert not gs['active'] and not gs['pending'] and not gs['waiting']
    assert all(x==allcpu[0] for x in allcpu)
    assert all(x['execution']==identities[0]['execution'] and set(x['service'])==set(identities[0]['service']) for x in identities)
    structure=closed['error'] is None and read(root/'block-0/service-cleanup.json')['gpu_clean']
    by,contrasts,passed=quality(rows)
    actual=all(any(e['index']//8==b and e['role']=='improve' and e['success'] for e in calls) for b in range(4))
    dispatched=all(q['co_admissions']>0 for q in queues if q['pool_mode']=='colocated')
    coexistence=read(root/'coexistence-qualification.json');assert coexistence['passed'] and coexistence['containers']==2
    write(out/'coexistence.json',coexistence)
    result.update(by_pool=by,contrasts=contrasts,quality_gate=passed,structural_gate=structure,
        runtime_input_gate=inputs_ok,actual_mode_gate=actual,dispatch_changed=dispatched,queues=queues,
        predeclared_success_gate_met=bool(passed and structure and inputs_ok and actual and dispatched))
    write(out/'identity.json',identities);write(out/'bindings.json',bindings);write(out/'summary.json',result)
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('root');ap.add_argument('out');ap.add_argument('--gpu-seconds',type=int,required=True)
    a=ap.parse_args();analyze(a.root,a.out,a.gpu_seconds)
