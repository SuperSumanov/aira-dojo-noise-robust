"""Complete-denominator readout of the local request deadline screen."""
import csv,json,statistics,sys
from pathlib import Path
from lifecycle_pilot import read,write,sha
from live_readout import finite,ground_scores,queue_verify,lines,timely_returns
from image_dev_data_20261011 import TASKS,score_at

ARMS=('deadline240','deadline600')


def summarize(rows):
    assert len(rows)==16 and len({r['index'] for r in rows})==16
    aggregates={};pairs=[]
    for arm in ARMS:
        rs=[r for r in rows if r['arm']==arm];assert len(rs)==8
        aggregates[arm]=dict(assigned=8,started=sum(r['started'] for r in rs),
            complete=sum(r['complete'] for r in rs),valid_endpoints=sum(r['complete'] and r['valid'] for r in rs),
            first_generation_failed=sum(r['first_generation_failed'] for r in rs),
            valid_returns=sum(r['valid_returns'] for r in rs),
            per_task_valid={t:sum(r['complete'] and r['valid'] for r in rs if r['task']==t) for t in TASKS})
    for lane in range(4):
        for task in TASKS:
            p={r['arm']:r for r in rows if r['lane']==lane and r['task']==task};a,b=(p[x] for x in ARMS)
            assert a['seed']==b['seed']
            av=a['complete'] and a['valid'] and finite(a['score']);bv=b['complete'] and b['valid'] and finite(b['score'])
            delta=(-1 if task==TASKS[1] else 1)*(b['score']-a['score']) if av and bv else None
            pairs.append(dict(task=task,lane=lane,seed=a['seed'],oriented_delta=delta,
                endpoint_coverage_delta=int(bv)-int(av) if a['started'] and b['started'] else None))
    a,b=(aggregates[x] for x in ARMS)
    gate=all(r['started'] for r in rows) and b['first_generation_failed']<a['first_generation_failed'] and b['valid_endpoints']>a['valid_endpoints'] and all(b['per_task_valid'][t]>=a['per_task_valid'][t] for t in TASKS)
    differences={t:[p['oriented_delta'] for p in pairs if p['task']==t and finite(p['oriented_delta'])] for t in TASKS}
    return dict(assigned=16,by_arm=aggregates,pairs=pairs,
        paired_medians={t:statistics.median(v) if v else None for t,v in differences.items()},
        paired_sample_sd={t:statistics.stdev(v) if len(v)>1 else None for t,v in differences.items()},
        screen_positive_before_structure=bool(gate),independent_pool_pairs=1,
        limitation='Exploratory fixed-order single-pool-pair timeout screen. No scheduling superiority or general method claim. Missing scores are not zero and are not excluded from assigned denominators.')


def analyze(root,output,gpu_seconds):
    root=Path(root);p=read(root/'plan.json');closed=read(root/'closed.json')
    assert p['planned']==16 and 0<=gpu_seconds<=p['allocation_seconds']*6
    for name,pin in p['files'].items():assert sha(root/name)==pin
    for name,pin in p['input_files'].items():assert sha(root/name)==pin
    spec=read(root/'dev-views/spec.json');rows=[];count=0;cpu_checks=[]
    from live_identity import cores
    for row in p['schedule']:
        ep=root/f"episode-{row['index']}";f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        closure=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        candidates=[read(q) for q in ep.glob('candidate-*.json') if '.private.' not in q.name]
        timely=timely_returns(candidates,p['run_seconds']);receipts=[]
        for path in sorted(ep.glob('scored-*.json')):
            saved=read(path);receipt=saved['receipt'];receipts.append(receipt)
            actual=score_at(root,spec,row['task'],ep/(path.stem+'.private.csv'));metric=spec[row['task']]['metric_name']
            assert actual['submission_sha256']==receipt['submission_sha256'] and abs(actual[metric]-receipt[metric])<=1e-12
            count+=1
        events=lines(ep/'events.jsonl');first=next((e for e in events if e['event']=='generation_returned' and e['call']==0),None)
        complete=closure.get('returncode')==0 and closure.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted')
        rows.append(dict(row,started=(ep/'deadline.json').exists(),complete=complete,
            valid=f.get('native_selected_valid',False),score=f.get('native_selected_score'),
            first_generation_failed=first is not None and not first['success'],
            first_generation_seconds=first['seconds'] if first else None,
            valid_returns=sum(x['valid'] for x in timely),candidate_returns=len(timely),late_returns=len(candidates)-len(timely),
            score_grounded=ground_scores(f,timely,receipts),cleanup=closure.get('cleanup_verified',False),source_commit=p['source_commit']))
    budgets=[]
    for block in range(2):
        bd=root/f'block-{block}';slot=read(bd/'budget-slot.json') if (bd/'budget-slot.json').exists() else {}
        steps=read(bd/'steps.json') if (bd/'steps.json').exists() else {}
        queues=[queue_verify(lines(root/f'queue-{block}-{lane}/events.jsonl'),2) for lane in range(4)]
        budgets.append(slot.get('reserved_seconds')==p['slot_seconds'] and p['slot_seconds']<=slot.get('actual_seconds',0)<=p['slot_seconds']+2 and steps.get('returncodes')==[0]*4 and all(q['complete'] for q in queues))
        for lane in range(4):
            paths=[root/f'episode-{8*block+2*lane+k}/cpu-partition.json' for k in (0,1)]
            if not all(x.exists() for x in paths):cpu_checks.append(False);continue
            a,b=(read(x) for x in paths);ac,bc=cores(a['worker_topology']),cores(b['worker_topology'])
            cpu_checks.append(len(ac)==len(bc)==2 and not ac&bc and ac|bc==cores(a['parent_topology'])==cores(b['parent_topology']))
    summary=summarize(rows);structural=all(budgets) and all(cpu_checks) and all(r['cleanup'] and r['score_grounded'] and not r['late_returns'] for r in rows) and closed['error'] is None
    summary.update(structural_complete=structural,scores_recomputed=count,cpu_pairs_checked=8,cpu_pairs_passed=sum(cpu_checks),
        plan_sha256=sha(root/'plan.json'),source_commit=p['source_commit'],gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
        screen_positive=summary['screen_positive_before_structure'] and structural,no_auto_expansion=True)
    output=Path(output);output.mkdir();write(output/'summary.json',summary);write(output/'runs.json',rows)
    with (output/'runs.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(summary,allow_nan=False))


if __name__=='__main__':analyze(sys.argv[1],sys.argv[2],int(sys.argv[3]))
