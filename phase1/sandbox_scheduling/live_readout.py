"""Frozen readout: all assignments, finite paired scores, independent queue replay.

No policy/candidate text, predictions, hidden labels or generation responses are
read/exported. Development score summaries belong only to this fresh live batch.
"""
import argparse
import csv
import datetime
import json
import math
from pathlib import Path
import statistics
from lifecycle_pilot import read, write, sha


def lines(path):
    if not path.exists():return []
    return [json.loads(v) for v in path.read_text().splitlines() if v.strip()]


def queue_verify(events,width):
    waiting=[];running={};seen=set();peak=0;waits=[];spans=[];last=-math.inf
    queued_at={}
    for e in events:
        t=e['time'];k=e['key'];action=e['event']
        if not math.isfinite(t) or t<last:raise ValueError('queue clock moved backwards')
        last=t
        if action=='queued':
            if k in seen:raise ValueError('duplicate queue identity')
            seen.add(k);waiting.append(k);queued_at[k]=t
        elif action=='admitted':
            if not waiting or waiting.pop(0)!=k or len(running)>=width:raise ValueError('FIFO/capacity violation')
            running[k]=t;waits.append(t-queued_at[k]);peak=max(peak,len(running))
        elif action=='released':
            if k not in running:raise ValueError('release without admission')
            spans.append({'key':k,'start':running.pop(k),'end':t})
        elif action=='queue_cancelled':
            if k not in waiting:raise ValueError('cancelled owner')
            waiting.remove(k)
        else:raise ValueError('unknown queue event')
        if e['active']!=len(running) or e['queued']!=len(waiting) or e['limit']!=width:
            raise ValueError('queue count mismatch')
    return dict(complete=not waiting and not running,admitted=len(waits),released=len(spans),peak=peak,
                queue_seconds=sum(waits),wait_median=None if not waits else statistics.median(waits),
                lease_seconds=sum(s['end']-s['start'] for s in spans))


def finite(v):return type(v) in (float,int) and math.isfinite(v)


def ground_scores(finished,timely,receipts):
    for candidate in timely:
        if not candidate['valid']:continue
        aux=candidate['aux'];metric=aux['metric_name']
        if not any(r.get('submission_sha256')==aux['submission_sha256']
                   and finite(r.get(metric)) and r[metric]==candidate['score'] for r in receipts):
            raise ValueError('candidate score not grounded in external dev receipt')
    return not finished.get('native_selected_valid',False) or any(
        x['valid'] is True and x.get('code_sha256')==finished.get('native_selected_code_sha256')
        and finite(x.get('score')) and x['score']==finished.get('native_selected_score') for x in timely)


def summarize(rows,blocks,arms=('pipeline','share2')):
    # Pool-level replication, not a test treating correlated runs as independent.
    diffs=[];raw_diffs=[];score_diffs={t:[] for t in sorted({r['task'] for r in rows})}
    attempted={b['block'] for b in blocks if b.get('attempted') is True}
    all_pairs=True
    if len(arms)!=2 or len(set(arms))!=2:raise ValueError('two named arms required')
    lower,wider=arms
    for repeat in (0,1):
        selected=[r for r in rows if r['repeat']==repeat]
        totals={a:sum(r['valid_returns'] for r in selected if r['arm']==a) for a in arms}
        raw_diffs.append(totals[wider]-totals[lower])
        # Absence of a launched comparator is not an observed zero return.
        # Retain assigned counts, including failures, separately; never rescue
        # a partial batch by summarizing only its completed pool pair.
        diffs.append(raw_diffs[-1] if {2*repeat,2*repeat+1} <= attempted else None)
        for slot in range(4):
            pair={r['arm']:r for r in selected if r['slot']==slot}
            a,b=pair[lower],pair[wider]
            if not all(r['native_valid'] and finite(r['native_score']) and r['complete'] for r in (a,b)):
                all_pairs=False;continue
            sign=-1 if a['task']=='spooky-author-identification' else 1
            score_diffs[a['task']].append(sign*(b['native_score']-a['native_score']))
    medians={t:None if not ds else statistics.median(ds) for t,ds in score_diffs.items()}
    completeness=len(rows)==16 and all(r['complete'] for r in rows)
    structural=len(blocks)==4 and all(b['queue']['complete'] and b['closed'] and b['identities_ok'] for b in blocks)
    return dict(assigned=16,complete=sum(r['complete'] for r in rows),
        assigned_pool_return_count_differences=raw_diffs,
        paired_pool_valid_return_differences=diffs,
        observed_pool_pairs=sum(v is not None for v in diffs),
        pool_difference_median=statistics.median(diffs) if all(v is not None for v in diffs) else None,
        pool_difference_sample_std=statistics.stdev(diffs) if all(v is not None for v in diffs) else None,
        paired_task_oriented_score_differences=score_diffs,paired_task_medians=medians,
        all_eight_score_pairs_observed=all_pairs,structural_audit=structural,
        exploratory_go=bool(completeness and structural and all_pairs and all(v is not None and v>0 for v in diffs)
                           and all(v is not None and v>=0 for v in medians.values())),
        boundary='Two paired scheduling blocks, reused development tasks. No population significance, neural-workload replication or new-method claim.')


def timely_returns(candidates,seconds):
    if type(seconds) is not int or seconds<=0:raise ValueError('declared positive run budget')
    if any(not finite(x.get('elapsed_seconds')) or x['elapsed_seconds']<0 for x in candidates):
        raise ValueError('invalid return timestamp')
    return [x for x in candidates if x['elapsed_seconds']<=seconds]


def analyze(root,output,*,allocation_gpu_seconds):
    root=Path(root);output=Path(output)
    closed=read(root/'closed.json');plan=read(root/'plan.json')
    limits=plan.get('admission_limits',{'pipeline':1,'share2':2})
    arms=tuple(sorted(limits,key=limits.get))
    if len(arms)!=2 or len(set(limits.values()))!=2:raise ValueError('two distinct permit limits')
    if len(plan['schedule'])!=16 or plan['gpus']!=3:raise ValueError('wrong trial')
    if plan.get('node_qualification_required'):
        qualification=read(root/'node-qualification.json') if (root/'node-qualification.json').exists() else {}
        if closed['attempted_blocks'] and (qualification.get('complete') is not True
                or qualification.get('task_image_sha256')!=plan['task_image_sha256']):
            raise ValueError('live block without original-image node qualification')
    if not 0<=allocation_gpu_seconds<=3*plan['allocation_seconds']:raise ValueError('invalid allocation accounting')
    for name,pin in plan['files'].items():
        if sha(root/name)!=pin:raise ValueError('frozen trial file changed')
    for name,pin in plan['public_inputs'].items():
        if sha(name)!=pin:raise ValueError('input drift')
    rows=[];blocks=[]
    for s in plan['schedule']:
        ep=root/f'episode-{s["index"]}'
        f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        c=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        candidates=[read(p) for p in sorted(ep.glob('candidate-*.json')) if '.private.' not in p.name]
        timely=timely_returns(candidates,plan.get('run_seconds',600))
        events=lines(ep/'events.jsonl')
        receipts=[read(p)['receipt'] for p in ep.glob('scored-*.json')]
        selected_verified=ground_scores(f,timely,receipts)
        row=dict(**s,source_commit=plan['source_commit'],run_seconds=plan.get('run_seconds',600),
            complete=c.get('returncode')==0 and c.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted'),
            native_valid=f.get('native_selected_valid') is True,native_score=f.get('native_selected_score'),
            native_score_verified=selected_verified,
            candidate_returns=len(timely),valid_returns=sum(x['valid'] is True for x in timely),
            late_returns=len(candidates)-len(timely),attempted=len(list(ep.glob('candidate-*.private.json'))),
            generation_calls=sum(e['event']=='generation_started' for e in events),
            generation_returned=sum(e['event']=='generation_returned' for e in events),
            generation_seconds=sum(e['seconds'] for e in events if e['event']=='generation_returned'),
            queue_seconds=sum(e.get('wait_seconds',0) for e in events if e['event'] in ('admitted','admission_interrupted')),
            cleanup_failures=sum(e['event']=='cleanup' and not e['verified'] for e in events))
        if row['native_valid'] and not finite(row['native_score']):raise ValueError('nonfinite selected score')
        if row['late_returns'] or not selected_verified:row['complete']=False
        rows.append(row)
    for block in range(4):
        bd=root/f'block-{block}';brows=[r for r in rows if r['block']==block];width=limits[brows[0]['arm']]
        events=lines(root/f'queue-{block}/events.jsonl');queue=queue_verify(events,width)
        c=read(bd/'closed.json') if (bd/'closed.json').exists() else {}
        execution=read(bd/'execution-native.json') if (bd/'execution-native.json').exists() else {}
        service=read(bd/'service-native.json') if (bd/'service-native.json').exists() else {}
        service_cleanup=read(bd/'service-cleanup.json') if (bd/'service-cleanup.json').exists() else {}
        workers=[]
        for row in brows:
            native=root/f'episode-{row["index"]}/native.json'
            if native.exists():workers.append(read(native))
        from live_identity import verify
        identity_ok=verify(execution,service,workers)
        slot=read(bd/'budget-slot.json') if (bd/'budget-slot.json').exists() else {}
        budget_ok=not plan.get('fixed_block_seconds') or (slot.get('reserved_seconds')==plan['fixed_block_seconds']
            and plan['fixed_block_seconds']<=slot.get('actual_seconds',0)<=plan['fixed_block_seconds']+2)
        blocks.append(dict(block=block,arm=brows[0]['arm'],queue=queue,attempted=block in closed['attempted_blocks'],
            closed=c.get('gpu_clean') is True and service_cleanup.get('gpu_clean') is True and not c.get('telemetry_errors') and (bd/'cycle-closed.json').exists() and budget_ok,
            identities_ok=bool(identity_ok),valid_returns=sum(r['valid_returns'] for r in brows)))
    result=summarize(rows,blocks,arms)
    if plan.get('fixed_block_seconds'):
        coverage=[]
        for rep in (0,1):
            totals={a:sum(r['native_valid'] and r['complete'] for r in rows if r['repeat']==rep and r['arm']==a)
                    for a in arms}
            coverage.append(totals[arms[1]]-totals[arms[0]])
        result.update(fixed_block_seconds=plan['fixed_block_seconds'],paired_valid_endpoint_differences=coverage,
            feedback_throughput_signal=bool(result['complete']==16 and result['structural_audit']
                and closed.get('controller_error') is None
                and all(d is not None and d>0 for d in result['paired_pool_valid_return_differences'])
                and all(d>=0 for d in coverage)))
    result.update(admission_limits=limits,plan_sha256=sha(root/'plan.json'),source_commit=plan['source_commit'],
                  readout_source_sha256=sha(__file__),
                  closed_sha256=sha(root/'closed.json'),allocation_gpu_seconds=allocation_gpu_seconds,
                  allocation_gpu_hours=allocation_gpu_seconds/3600,controller_error=closed.get('controller_error'),
                  readout_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if result['controller_error'] is not None:result['exploratory_go']=False
    output.mkdir(exist_ok=False)
    write(output/'summary.json',result);write(output/'blocks.json',blocks);write(output/'runs.json',rows)
    with (output/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('output');p.add_argument('--allocation-gpu-seconds',type=int,required=True)
    a=p.parse_args();analyze(a.root,a.output,allocation_gpu_seconds=a.allocation_gpu_seconds)
