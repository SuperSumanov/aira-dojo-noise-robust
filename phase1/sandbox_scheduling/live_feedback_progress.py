"""Post-closure v7 feedback-to-next-execution exposure, not a causal mediator.

Uses all16 assigned fresh R14 dev runs. No raw program, generation, label or
prediction export. This is not a revival of September action-delivery research.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/scheduling-live-search-20261009-v7')
PLAN='86aa8f7a3d534ef1eaaa5475482a8838fe29c06f1ee30cb367cc05aae411c774'
PRIMARY='f662677995ab85a61766dbf271cf2b93db89f9937c57a7048414d324e96eb859'
ROLES=('draft','debug','improve','analysis')


def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def progress(events,candidates,horizon=600):
    last=-math.inf
    for e in events:
        if not math.isfinite(e['elapsed']) or e['elapsed'] < last:
            raise ValueError('event clock')
        last=e['elapsed']
    returned=sorted(candidates,key=lambda c:c['elapsed_seconds'])
    if any(not math.isfinite(c['elapsed_seconds']) or c['elapsed_seconds'] < 0
           or type(c['valid']) is not bool for c in returned):
        raise ValueError('invalid candidate receipt')
    operations=[e for e in events if e['event']=='operation_ready' and e['kind']=='candidate']
    result=[]
    for c in returned:
        t=c['elapsed_seconds']
        if t>horizon: raise ValueError('late return cannot be silently dropped')
        later=[e for e in operations if t<e['elapsed']<=horizon]
        next_op=later[0] if later else None
        end=next_op['elapsed'] if next_op else horizon
        starts=[e for e in events if e['event']=='generation_started' and t<e['elapsed']<=end]
        calls={e['call'] for e in starts}
        completed=[e for e in events if e['event']=='generation_returned' and e['call'] in calls and e['elapsed']<=end]
        admitted=next((e for e in events if next_op and e['event']=='admitted' and e['operation']==next_op['operation']),None)
        next_returns=[x for x in returned if next_op and next_op['elapsed']<x['elapsed_seconds']<=horizon]
        # No claim that elapsed-order proves feedback was semantically used.
        result.append(dict(valid=c['valid'],returned_seconds=t,
            next_generation_started=bool(starts),generation_calls_before_next_operation=len(starts),
            completed_generation_calls_before_next_operation=len(completed),
            next_candidate_operation_ready_seconds=None if next_op is None else next_op['elapsed'],
            next_candidate_admitted_seconds=None if admitted is None else admitted['elapsed'],
            subsequent_candidate_returned=bool(next_returns),
            next_return_valid=None if not next_returns else next_returns[0]['valid']))
    return result


def recorded_roles(nodes):
    totals={r:dict(calls=0,prompt_tokens=0,completion_tokens=0,latency_seconds=0.,missing_usage=0) for r in ROLES}
    seen=set()
    for node in nodes:
        names=node.get('operators_used',[]);metrics=node.get('operators_metrics',[])
        if len(names)!=len(metrics):raise ValueError('role metrics shape')
        for name,metric in zip(names,metrics):
            if name not in totals:raise ValueError('unknown role')
            usage=metric.get('usage',{});identity=usage.get('attempt_id')
            if identity:
                if identity in seen:raise ValueError('duplicate recorded call')
                seen.add(identity)
            row=totals[name];row['calls']+=1
            if any(type(usage.get(k)) is not int for k in ('prompt_tokens','completion_tokens')):row['missing_usage']+=1
            for key in ('prompt_tokens','completion_tokens'):
                value=usage.get(key)
                if type(value) is int:
                    if value<0:raise ValueError('negative usage')
                    row[key]+=value
            value=usage.get('latency')
            if type(value) in (int,float) and math.isfinite(value):
                if value<0:raise ValueError('negative latency')
                row['latency_seconds']+=value
    return totals


def main():
    if sha(ROOT/'plan.json')!=PLAN or sha(ROOT/'readout-v1/summary.json')!=PRIMARY:
        raise ValueError('closed v7 only')
    plan=read(ROOT/'plan.json');primary=read(ROOT/'readout-v1/summary.json')
    if primary['complete']!=16:raise ValueError('full closed cohort')
    rows=[]
    for row in plan['schedule']:
        ep=ROOT/f'episode-{row["index"]}'
        events=[json.loads(s) for s in (ep/'events.jsonl').read_text().splitlines()]
        candidates=[read(p) for p in sorted(ep.glob('candidate-*.json')) if '.private.' not in p.name]
        journal=ep/'checkpoint/journal.jsonl'
        nodes=[json.loads(s) for s in journal.read_text().splitlines() if s.strip()] if journal.exists() else []
        hashed={hashlib.sha256(n['code'].encode()).hexdigest() for n in nodes if isinstance(n.get('code'),str)}
        progression=progress(events,candidates,plan['run_seconds'])
        valid=[c for c in candidates if c['valid']]
        rows.append(dict(**row,event_sha256=sha(ep/'events.jsonl'),
            journal_exists=journal.exists(),journal_sha256=sha(journal) if journal.exists() else None,
            candidate_returns=len(candidates),valid_returns=len(valid),
            exact_valid_return_codes_missing_from_final_journal=sum(c['code_sha256'] not in hashed for c in valid),
            generation_calls=sum(e['event']=='generation_started' for e in events),
            recorded_node_calls=recorded_roles(nodes),feedback_progression=progression,
            timely_valid_feedback_followed_by_next_generation=sum(p['valid'] and p['next_generation_started'] for p in progression),
            timely_valid_feedback_followed_by_next_operation=sum(p['valid'] and p['next_candidate_operation_ready_seconds'] is not None for p in progression),
            timely_valid_feedback_followed_by_next_return=sum(p['valid'] and p['subsequent_candidate_returned'] for p in progression)))
    blocks=[]
    keys=('candidate_returns','valid_returns','exact_valid_return_codes_missing_from_final_journal',
          'generation_calls','timely_valid_feedback_followed_by_next_generation',
          'timely_valid_feedback_followed_by_next_operation','timely_valid_feedback_followed_by_next_return')
    for b in range(4):
        own=[r for r in rows if r['block']==b]
        blocks.append(dict(block=b,arm=own[0]['arm'],**{k:sum(r[k] for r in own) for k in keys}))
    result=dict(plan_sha256=PLAN,frozen_primary_sha256=PRIMARY,analysis_sha256=sha(Path(__file__)),rows=rows,blocks=blocks,
        boundary='Post-result descriptive exposure; no counterfactual shifting/replay, no change of frozen gates. Event order does not establish semantic feedback use or mediation. Recorded-node role usage can miss interrupted calls; not total cost. Missing exact-code match may reflect representation, not proven lost solution. September action-delivery result is prior engineering evidence, not a new mechanism here.')
    dest=ROOT/'feedback-progress-v1.json'
    with dest.open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(dict(written=True,sha256=sha(dest),blocks=blocks)))


if __name__=='__main__':main()
