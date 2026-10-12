"""Missing-aware readout after infrastructure closure, before any quality read.

The original48-assignment success gate cannot pass. No missing comparator is
replaced by the warm score. Only wholly qualified equal-budget pools compare.
The planned full reader and live experiment remain unchanged.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys

from feedback_parent_readout_20261012 import read, write, sha, lines, audit, ARMS, ORDER, TASKS, SIGN
from feedback_parent_mechanism_20261012 import analyze_events
from feedback_parent_secondary_20261012 import duplicates


def compare_available(scores, qualified):
    contrasts=[]
    for rep in range(2):
        blocks={ORDER[b]:b for b in range(rep*3,rep*3+3)}
        for task in TASKS:
            for ref in ARMS[:2]:
                a,b=blocks['feedback_gate'],blocks[ref]
                observed=qualified[a] and qualified[b]
                delta=SIGN[task]*(scores[a,task]-scores[b,task]) if observed else None
                margin=.001 if task==TASKS[1] else -1e-12
                contrasts.append(dict(repeat=rep,task=task,reference=ref,comparable=observed,
                    method_best=scores[a,task] if qualified[a] else None,
                    reference_best=scores[b,task] if qualified[b] else None,
                    oriented_delta=delta,meets_original_margin=delta>=margin if observed else None))
    observed=[r for r in contrasts if r['comparable']]
    return dict(contrasts=contrasts,comparable_contrasts=len(observed),
        observed_margin_failures=sum(not r['meets_original_margin'] for r in observed),
        full_quality_comparison_available=len(observed)==8,
        first_repeat_meets_quality_rule=all(r['comparable'] and r['meets_original_margin'] for r in contrasts if r['repeat']==0),
        predeclared_success_gate_met=False,no_automatic_expansion=True)


def analyze(root,output,gpu_seconds):
    root,output=Path(root),Path(output)
    p,closed=read(root/'plan.json'),read(root/'closed.json')
    assert p['planned']==48 and p['allocation_seconds']==7800
    assert closed['complete']==39 and closed['attempted_blocks']==[0,1,2,3,4]
    assert 0<gpu_seconds<=7800*6
    assert all(sha(root/n)==h for n,h in p['files'].items())
    assert all(sha(root/n)==h for n,h in p['input_files'].items())
    sys.path.insert(0,str(root))
    from image_dev_data_20261011 import score_at
    from live_readout import timely_returns,ground_scores,queue_verify
    from live_identity import cores
    spec,warm=read(root/'dev-views/spec.json'),read(root/'warm-receipt.json')
    rows=[];recomputed=0
    for s in p['schedule']:
        ep=root/f"episode-{s['index']}";started=(ep/'deadline.json').exists()
        f=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        c=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        cs=[read(x) for x in ep.glob('candidate-*.json') if '.private.' not in x.name]
        timely=timely_returns(cs,1020);receipts=[]
        for x in ep.glob('scored-*.json'):
            receipt=read(x)['receipt'];receipts.append(receipt)
            actual=score_at(root,spec,s['task'],ep/(x.stem+'.private.csv'));metric=spec[s['task']]['metric_name']
            assert actual['submission_sha256']==receipt['submission_sha256']
            assert abs(actual[metric]-receipt[metric])<=1e-12
            recomputed+=1
        assert ground_scores(dict(f,native_selected_valid=False),timely,receipts)
        eligible=[r['score'] for r in timely if r.get('valid') is True and r.get('exit_code')==0 and not r.get('timed_out') and isinstance(r.get('score'),(int,float)) and math.isfinite(r['score'])]
        initial=warm[s['task']]['score']
        score=max([initial]+eligible,key=lambda v:SIGN[s['task']]*v) if started else None
        rows.append(dict(s,source_commit=p['source_commit'],run_seconds=1020,pool_seconds=1180,
            score=score,initial_score=initial,started=started,
            complete=c.get('returncode')==0 and c.get('cleanup_verified') is True and f.get('status') in ('completed','budget_exhausted'),
            returncode=c.get('returncode'),cleanup=c.get('cleanup_verified') is True,
            candidate_returns=len(timely),valid_returns=len(eligible)))
    qualified={};blocks=[];identities=[];scores={};mechanisms=[]
    for b in range(6):
        bd=root/f'block-{b}';attempted=b in closed['attempted_blocks'];rr=[r for r in rows if r['block']==b]
        slot=read(bd/'budget-slot.json') if (bd/'budget-slot.json').exists() else {}
        steps=read(bd/'steps.json') if (bd/'steps.json').exists() else {}
        queues=[];cpu=[];identity_ok=False;policy=None
        if attempted:
            sv=read(bd/'service-native.json');ls=[read(bd/f'lane-{i}-native.json') for i in range(4)]
            sets=[cores(x['cpu_topology']) for x in ls]+[cores(sv['cpu_topology'])]
            identity=dict(block=b,lanes=[x['gpu_uuid'] for x in ls],service=sv['gpu_uuids'])
            identity_ok=len(set(identity['lanes']))==4 and len(set(identity['service']))==2 and not set(identity['lanes'])&set(identity['service'])
            identity_ok=identity_ok and [len(x) for x in sets]==[4,4,4,4,8] and all(not sets[i]&sets[j] for i in range(5) for j in range(i))
            if identities:identity_ok=identity_ok and identity['lanes']==identities[0]['lanes'] and set(identity['service'])==set(identities[0]['service'])
            identity['valid']=bool(identity_ok);identities.append(identity)
            for lane in range(4):
                try:queues.append(dict(**queue_verify(lines(root/f'queue-{b}-{lane}/events.jsonl'),1),audit_error=None))
                except (AssertionError,ValueError,KeyError) as e:queues.append(dict(complete=False,audit_error=type(e).__name__))
                a,c=(read(root/f'episode-{8*b+2*lane+k}/cpu-partition.json') for k in (0,1))
                ac,cc=cores(a['worker_topology']),cores(c['worker_topology'])
                cpu.append(len(ac)==len(cc)==2 and not ac&cc and ac|cc==cores(a['parent_topology'])==cores(c['parent_topology']))
            es=lines(root/f'generation-{b}/events.jsonl')
            policy=audit(es,ORDER[b])
            by_task={}
            for task in TASKS:
                sr=[r for r in p['schedule'] if (r['block'],r['task'])==(b,task)]
                ids={r['index'] for r in sr};ev=[e for e in es if e['run'] in ids]
                by_task[task]=dict(**analyze_events(ev,sr,ORDER[b]),**duplicates(ev))
            mechanisms.append(dict(block=b,arm=ORDER[b],policy=policy,by_task=by_task))
        equal=slot.get('reserved_seconds')==1180 and 1180<=slot.get('actual_seconds',-1)<=1182
        qualified[b]=bool(attempted and equal and steps.get('returncodes')==[0]*4 and all(r['complete'] for r in rr) and identity_ok and all(cpu) and all(q['complete'] for q in queues))
        # The failing/unstarted pools remain in the denominator, but do not
        # acquire a fabricated equal-budget comparison endpoint.
        for task in TASKS:
            scores[b,task]=max([r['score'] for r in rr if r['task']==task],key=lambda v:SIGN[task]*v) if qualified[b] else None
        blocks.append(dict(block=b,arm=ORDER[b],attempted=attempted,equal_budget_closed=equal,
            qualified=qualified[b],complete=sum(r['complete'] for r in rr),queues=queues,cpu_pairs_passed=sum(cpu),
            identity_ok=bool(identity_ok),scores={t:scores[b,t] for t in TASKS}))
    assert [b for b in qualified if qualified[b]]==[0,1,2,3]
    result=compare_available(scores,qualified)
    result.update(assigned=48,started=sum(r['started'] for r in rows),complete=sum(r['complete'] for r in rows),
        source_commit=p['source_commit'],plan_sha256=sha(root/'plan.json'),readout_sha256=sha(__file__),
        original_reader_sha256=sha(root/'feedback_parent_readout_20261012.py'),
        scores_recomputed=recomputed,blocks=blocks,mechanisms=mechanisms,
        structural_gate=False,gpu_seconds=gpu_seconds,gpu_hours=gpu_seconds/3600,
        service_gpu_clean=read(root/'block-0/service-cleanup.json')['gpu_clean'],
        qualified_run_summary={a:{t:dict(n=len(v),median=statistics.median(v),sample_sd=statistics.stdev(v))
            for t in TASKS for v in [[r['score'] for r in rows if r['arm']==a and r['task']==t and qualified[r['block']]]]} for a in ARMS},
        limitation='Post-infrastructure-closure, pre-quality-read partial analysis. Only the first repeat has both whole-budget references. No two-repeat confirmation, no missing arm imputation, no original-gate rescue. Development checkpoint-conditioned search, not official test or SOTA proof.')
    output.mkdir()
    write(output/'summary.json',result);write(output/'runs.json',rows);write(output/'identity.json',identities)
    with (output/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('output');p.add_argument('--gpu-seconds',type=int,required=True)
    a=p.parse_args();analyze(a.root,a.output,a.gpu_seconds)
