"""Frozen32-run quality-first readout; no rescue of prior batches."""
import csv,json,statistics,sys
from pathlib import Path
from lifecycle_pilot import read,write,sha
from live_readout import finite,ground_scores,queue_verify,lines,timely_returns
from image_dev_data_20261011 import TASKS,score_at

ARMS=('deadline240','deadline600');MARGIN={t:0.001 for t in TASKS}


def valid(r):return r['complete'] and r['valid'] and finite(r['score'])


def distribution(values):
    return dict(n=len(values),median=statistics.median(values) if values else None,
        sample_sd=statistics.stdev(values) if len(values)>1 else None)


def summarize(rows):
    assert len(rows)==32 and {r['index'] for r in rows}==set(range(32))
    assert len({(r['repeat'],r['task'],r['lane'],r['arm']) for r in rows})==32
    pools=[];pairs=[];aggregates={}
    for arm in ARMS:
        rs=[r for r in rows if r['arm']==arm];assert len(rs)==16
        aggregates[arm]=dict(assigned=16,started=sum(r['started'] for r in rs),complete=sum(r['complete'] for r in rs),
            valid_endpoints=sum(valid(r) for r in rs),valid_returns=sum(r['valid_returns'] for r in rs),
            first_generation_failed=sum(r['first_generation_failed'] for r in rs),
            task_score_descriptive={t:distribution([r['score'] for r in rs if r['task']==t and valid(r)]) for t in TASKS})
    for repeat in (0,1):
        for task in TASKS:
            sets={arm:[r for r in rows if (r['repeat'],r['task'],r['arm'])==(repeat,task,arm)] for arm in ARMS}
            assert all(len(v)==4 for v in sets.values())
            best={};coverage={}
            for arm,rs in sets.items():
                values=[r['score'] for r in rs if valid(r)];coverage[arm]=len(values)
                best[arm]=(min(values) if task==TASKS[1] else max(values)) if values else None
            delta=(1 if task==TASKS[0] else -1)*(best[ARMS[1]]-best[ARMS[0]]) if all(finite(x) for x in best.values()) else None
            pools.append(dict(repeat=repeat,task=task,assigned_per_arm=4,best_native_endpoint=best,valid_endpoint_count=coverage,oriented_delta=delta))
            for lane in range(4):
                a,b=(next(r for r in sets[arm] if r['lane']==lane) for arm in ARMS);assert a['seed']==b['seed']
                d=(1 if task==TASKS[0] else -1)*(b['score']-a['score']) if valid(a) and valid(b) else None
                pairs.append(dict(repeat=repeat,task=task,lane=lane,seed=a['seed'],oriented_delta=d,coverage_delta=int(valid(b))-int(valid(a)) if a['started'] and b['started'] else None))
    complete=all(finite(p['oriented_delta']) for p in pools)
    no_loss=complete and all(p['oriented_delta']>=-1e-12 for p in pools)
    repeated_material=complete and any(all(p['oriented_delta']>=MARGIN[t] for p in pools if p['task']==t) for t in TASKS)
    coverage_ok=all(p['valid_endpoint_count'][ARMS[1]]>=p['valid_endpoint_count'][ARMS[0]] for p in pools)
    quality=all(r['started'] for r in rows) and no_loss and repeated_material and coverage_ok
    return dict(assigned=32,independent_pool_pairs=2,order=['deadline240','deadline600','deadline600','deadline240'],
        by_arm=aggregates,pool_task_contrasts=pools,run_pairs=pairs,
        complete_pool_task_contrasts=sum(finite(p['oriented_delta']) for p in pools),
        complete_run_quality_pairs=sum(finite(p['oriented_delta']) for p in pairs),
        pool_delta_by_task={t:distribution([p['oriented_delta'] for p in pools if p['task']==t and finite(p['oriented_delta'])]) for t in TASKS},
        paired_run_delta_by_task={t:distribution([p['oriented_delta'] for p in pairs if p['task']==t and finite(p['oriented_delta'])]) for t in TASKS},
        practical_margin=MARGIN,all_pool_task_quality_comparable=complete,no_task_repeat_quality_loss=no_loss,
        same_task_material_gain_both_repeats=repeated_material,no_task_repeat_endpoint_loss=coverage_ok,
        quality_signal_before_structure=bool(quality),
        limitation='Two ABBA seed-set pool pairs on reused development tasks; not statistical confirmation or method novelty. Missing scores stay null. Complete-case run scores are descriptive, not population effects. Earlier17656 excluded.')


def analyze(root,output,gpu_seconds):
    root=Path(root);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert p['planned']==32 and p['allocation_seconds']==6120 and 0<=gpu_seconds<=6120*6
    assert p['practical_margin']==MARGIN
    for name,pin in p['files'].items():assert sha(root/name)==pin
    for name,pin in p['input_files'].items():assert sha(root/name)==pin
    spec=read(root/'dev-views/spec.json');rows=[];count=0;cpu_checks=[];identities=[]
    from live_identity import cores
    for row in p['schedule']:
        ep=root/f"episode-{row['index']}";f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        closure=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        candidates=[read(q) for q in ep.glob('candidate-*.json') if '.private.' not in q.name]
        timely=timely_returns(candidates,p['run_seconds']);receipts=[]
        for path in sorted(ep.glob('scored-*.json')):
            saved=read(path);receipt=saved['receipt'];receipts.append(receipt)
            actual=score_at(root,spec,row['task'],ep/(path.stem+'.private.csv'));metric=spec[row['task']]['metric_name']
            assert actual['submission_sha256']==receipt['submission_sha256'] and abs(actual[metric]-receipt[metric])<=1e-12;count+=1
        events=lines(ep/'events.jsonl');first=next((e for e in events if e['event']=='generation_returned' and e['call']==0),None)
        complete=closure.get('returncode')==0 and closure.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted')
        if f.get('native_selected_valid'):assert finite(f.get('native_selected_score'))
        rows.append(dict(row,started=(ep/'deadline.json').exists(),complete=complete,valid=f.get('native_selected_valid',False),score=f.get('native_selected_score'),
            first_generation_failed=first is not None and not first['success'],first_generation_seconds=first['seconds'] if first else None,
            valid_returns=sum(x['valid'] for x in timely),candidate_returns=len(timely),late_returns=len(candidates)-len(timely),
            score_grounded=ground_scores(f,timely,receipts),cleanup=closure.get('cleanup_verified',False),source_commit=p['source_commit']))
    budgets=[]
    for block in range(4):
        bd=root/f'block-{block}';slot=read(bd/'budget-slot.json') if (bd/'budget-slot.json').exists() else {}
        steps=read(bd/'steps.json') if (bd/'steps.json').exists() else {}
        queues=[queue_verify(lines(root/f'queue-{block}-{lane}/events.jsonl'),2) for lane in range(4)]
        budgets.append(slot.get('reserved_seconds')==1500 and 1500<=slot.get('actual_seconds',0)<=1502 and steps.get('returncodes')==[0]*4 and all(q['complete'] for q in queues))
        service=read(bd/'service-native.json') if (bd/'service-native.json').exists() else {}
        lanes=[read(bd/f'lane-{i}-native.json') if (bd/f'lane-{i}-native.json').exists() else {} for i in range(4)]
        sets=[cores(x.get('cpu_topology',[])) for x in lanes]+[cores(service.get('cpu_topology',[]))]
        devices=[x.get('gpu_uuid') for x in lanes];svc=service.get('gpu_uuids',[])
        okay=all(devices) and len(set(devices))==4 and len(set(svc))==2 and not set(devices)&set(svc) and all(len(s)==4 for s in sets[:4]) and len(sets[-1])==8 and all(not sets[i]&sets[j] for i in range(5) for j in range(i))
        cleanup=read(bd/'service-cleanup.json') if (bd/'service-cleanup.json').exists() else {}
        identities.append(dict(block=block,valid=bool(okay and cleanup.get('gpu_clean')),lanes=devices,service=svc))
        for lane in range(4):
            paths=[root/f'episode-{8*block+2*lane+k}/cpu-partition.json' for k in (0,1)]
            if not all(x.exists() for x in paths):cpu_checks.append(False);continue
            a,b=(read(x) for x in paths);ac,bc=cores(a['worker_topology']),cores(b['worker_topology'])
            cpu_checks.append(len(ac)==len(bc)==2 and not ac&bc and ac|bc==cores(a['parent_topology'])==cores(b['parent_topology']))
    physical=all(x['valid'] and x['lanes']==identities[0]['lanes'] and set(x['service'])==set(identities[0]['service']) for x in identities)
    summary=summarize(rows);structural=all(budgets) and all(cpu_checks) and physical and all(r['cleanup'] and r['score_grounded'] and not r['late_returns'] for r in rows) and closed['error'] is None
    summary.update(structural_complete=structural,scores_recomputed=count,cpu_pairs_checked=16,cpu_pairs_passed=sum(cpu_checks),physical_lane_identity_passed=physical,
        plan_sha256=sha(root/'plan.json'),source_commit=p['source_commit'],gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
        replicated_quality_signal=bool(summary['quality_signal_before_structure'] and structural),no_auto_expansion=True)
    output=Path(output);output.mkdir();write(output/'summary.json',summary);write(output/'runs.json',rows);write(output/'identity.json',identities)
    with (output/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,allow_nan=False))


if __name__=='__main__':analyze(sys.argv[1],sys.argv[2],int(sys.argv[3]))
