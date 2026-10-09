"""Pre-outcome qualification readout; no selected scores or candidate export."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from lifecycle_pilot import read,write,sha
from live_identity import verify
from live_readout import ground_scores,lines,queue_verify


def match_roles(nodes,candidates):
    # Native journal appends executed nodes. Match chronological receipts as a
    # subsequence, not a hash set that can relabel an earlier Draft as Improve.
    cursor=0;roles=Counter();matched=[];unknown=0
    for node in nodes:
        names=node.get('operators_used',[])
        if not names:continue
        if names[0] not in ('draft','debug','improve'):raise ValueError('unknown native operation')
        role=names[0];roles[role]+=1
        code=node.get('code')
        if not isinstance(code,str):unknown+=1;continue
        pin=hashlib.sha256(code.encode()).hexdigest()
        index=next((i for i in range(cursor,len(candidates)) if candidates[i]['code_sha256']==pin),None)
        if index is None:unknown+=1;continue
        cursor=index+1;c=candidates[index]
        matched.append(dict(role=role,valid=c['valid'],elapsed_seconds=c['elapsed_seconds']))
    return dict(recorded_roles=dict(roles),unmatched_recorded_nodes=unknown,matched=matched,
        completed_valid_improves=sum(x['role']=='improve' and x['valid'] for x in matched))


def qualify(rows,structural):
    tasks=sorted({r['task'] for r in rows})
    supported={task:any(r['task']==task and r['completed_valid_improves']>0 for r in rows) for task in tasks}
    return bool(len(rows)==4 and len(tasks)==2 and structural and all(r['complete'] and r['unmatched_recorded_nodes']==0 for r in rows) and all(supported.values())),supported


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--allocation-gpu-seconds',type=int,required=True);a=p.parse_args();R=a.root
    if sha(R/'plan.json')!=a.plan_sha256 or not 0<a.allocation_gpu_seconds<=11700:raise ValueError('pin/budget')
    plan=read(R/'plan.json');closed=read(R/'closed.json')
    if plan['run_seconds']!=3000 or len(plan['schedule'])!=4 or plan['admission_limits']!={'share2':2}:raise ValueError('scope')
    for name,pin in plan['files'].items():
        if sha(R/name)!=pin:raise ValueError('source drift')
    rows=[]
    for s in plan['schedule']:
        ep=R/f'episode-{s["index"]}';end=read(ep/'finished.json') if (ep/'finished.json').exists() else {}
        closure=read(ep/'closed.json') if (ep/'closed.json').exists() else {}
        cfg=read(R/f'configs/{s["index"]}.json')
        if cfg['solver']['time_limit_secs']!=3000 or cfg['solver']['num_children']!=5:raise ValueError('policy/budget')
        candidates=sorted([read(f) for f in ep.glob('candidate-*.json') if '.private.' not in f.name],key=lambda x:x['elapsed_seconds'])
        late=any(c['elapsed_seconds']>3000 for c in candidates)
        receipts=[read(f)['receipt'] for f in ep.glob('scored-*.json')]
        grounded=ground_scores(end,candidates,receipts)
        journal=ep/'checkpoint/journal.jsonl';nodes=lines(journal)
        roles=match_roles(nodes,candidates)
        events=lines(ep/'events.jsonl')
        rows.append(dict(**s,**roles,complete=closure.get('returncode')==0 and closure.get('cleanup_verified') is True
            and end.get('status') in ('completed','budget_exhausted') and not late and grounded,
            candidate_returns=len(candidates),valid_returns=sum(c['valid'] for c in candidates),
            readiness_failures=sum(e['event']=='kernel_ready' and not e['success'] for e in events),
            generation_calls=sum(e['event']=='generation_started' for e in events),
            journal_sha256=sha(journal) if journal.exists() else None,events_sha256=sha(ep/'events.jsonl') if (ep/'events.jsonl').exists() else None,
            num_children=5,run_seconds=3000))
    block=R/'block-0';b=read(block/'closed.json') if (block/'closed.json').exists() else {}
    identity=False;queue=None
    if b:
        identity=verify(read(block/'execution-native.json'),read(block/'service-native.json'),[read(R/f'episode-{i}/native.json') for i in range(4)])
        queue=queue_verify(lines(R/'queue-0/events.jsonl'),2)
    clean=read(block/'service-cleanup.json').get('gpu_clean') is True if (block/'service-cleanup.json').exists() else False
    structural=bool(b and identity and queue['complete'] and b.get('gpu_clean') and clean and not b.get('telemetry_errors')
        and closed['controller_error'] is None and closed['service_closed'])
    passed,tasks=qualify(rows,structural)
    result=dict(plan_sha256=a.plan_sha256,analysis_sha256=sha(Path(__file__)),closed_sha256=sha(R/'closed.json'),
        rows=rows,structural=structural,queue=queue,task_exposure=tasks,exposure_qualified=passed,
        allocation_gpu_seconds=a.allocation_gpu_seconds,allocation_gpu_hours=a.allocation_gpu_seconds/3600,
        boundary='Single-arm exposure only. No same-budget A/B, no new algorithm, no final-quality gain, no inference that extra time alone caused exposure (fresh seeds and prompt budget differ). Previous17308/v7 gates unchanged. Temporal follow-on does not prove semantic feedback use.')
    write(R/'exposure-readout-v1.json',result)
    print(json.dumps(dict(sha256=sha(R/'exposure-readout-v1.json'),assigned=4,rows=rows,exposure_qualified=passed,structural=structural)))


if __name__=='__main__':main()
