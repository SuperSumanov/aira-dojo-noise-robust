"""Read-only secondary descriptions; never alter the frozen primary analysis.

Specified before any result inspection. Node costs are lower bounds when an
in-flight/failed call was not journaled. They are not allocated GPU cost.
"""
import argparse, hashlib, json, math, re
from collections import Counter, defaultdict
from pathlib import Path

R=Path('/research/d7/spc/yzyang4/policy9b-paired-20261005-gpu27-v1')
ROLES=('draft','debug','improve','analysis')

def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize_nodes(nodes):
    seen=set();roles={r:dict(recorded_calls=0,prompt_tokens=0,completion_tokens=0,
        latency_seconds=0.,incomplete_usage=0) for r in ROLES}
    for n in nodes:
        names=n.get('operators_used',[]);metrics=n.get('operators_metrics',[])
        assert len(names)==len(metrics)
        for role,m in zip(names,metrics):
            assert role in ROLES
            usage=m.get('usage',{});attempt=usage.get('attempt_id')
            if attempt:
                assert attempt not in seen,'duplicate call in journal'
                seen.add(attempt)
            row=roles[role];row['recorded_calls']+=1
            if any(type(usage.get(k)) is not int for k in ('prompt_tokens','completion_tokens')):
                row['incomplete_usage']+=1
            for k in ('prompt_tokens','completion_tokens'):
                v=usage.get(k)
                if type(v) is int:assert v>=0;row[k]+=v
            v=usage.get('latency')
            if type(v) in (int,float) and math.isfinite(v):assert v>=0;row['latency_seconds']+=v
    return roles

def tests():
    n=dict(operators_used=['draft','analysis'],operators_metrics=[
        dict(usage=dict(attempt_id='a',prompt_tokens=10,completion_tokens=5,latency=2,cumulative_num_llm_calls=99)),
        dict(usage=dict(attempt_id='b',prompt_tokens=20,completion_tokens=3,latency=1))])
    rows=summarize_nodes([n]);assert rows['draft']['recorded_calls']==1 and rows['analysis']['completion_tokens']==3
    assert summarize_nodes([])['debug']['latency_seconds']==0
    assert summarize_nodes([dict(operators_used=['debug'],operators_metrics=[{}])])['debug']['incomplete_usage']==1
    try:summarize_nodes([n,n])
    except AssertionError:pass
    else:raise AssertionError('duplicate not rejected')
    print(json.dumps(dict(status='PASS',checks=4,result_values_read=0)))

def main():
    # The primary reader independently requires terminal Slurm + no queue + hashes.
    summary=read(R/'readout-v1/summary.json')
    assert summary['status']=='CLOSED_DEVELOPMENT_QUALIFICATION'
    assert summary['plan_sha256']==sha(R/'plan.json')
    plan=read(R/'plan.json');rows=[]
    for s in plan['schedule']:
        ep=R/f"episode-{s['index']}";journal=ep/'checkpoint/journal.jsonl'
        nodes=[json.loads(line) for line in journal.read_bytes().splitlines() if line.strip()] if journal.exists() else []
        candidates=[read(p) for p in ep.glob('candidate-*.json') if not p.name.endswith('.private.json')]
        scored=[read(p) for p in ep.glob('scored-*.json')]
        valid=[n for n in nodes if n.get('is_buggy') is False and type(n.get('metric')) in (int,float)]
        lower=s['task']=='spooky-author-identification'
        best=(min if lower else max)(valid,key=lambda n:n['metric']) if valid else None
        roles=summarize_nodes(nodes)
        row=dict(**s,recorded_node_calls=roles,
            selected_origin=None if best is None else best.get('operators_used',[None])[0],
            completed_candidate_records=len(candidates),execution_nonzero=sum(c.get('exit_code') not in (0,None) for c in candidates),
            execution_timeouts=sum(bool(c.get('timed_out')) for c in candidates),
            recorded_execution_seconds=sum(c.get('exec_seconds') or 0 for c in candidates),
            first_external_valid_elapsed=min((x['elapsed_seconds'] for x in scored),default=None),
            completed_candidate_elapsed=[c['elapsed_seconds'] for c in sorted(candidates,key=lambda c:c['elapsed_seconds'])],
            native_good_nodes=len(valid),completed_journal_nodes=max(len(nodes)-1,0),
            action_coverage=[role for role in ROLES[:-1] if roles[role]['recorded_calls']],
            cost_boundary='Recorded completed-node token/latency counts only; lost interrupted/failed calls may be absent. Allocated GPU-hours in frozen primary summary are complete.')
        rows.append(row)
    report=dict(protocol='secondary-descriptive-before-readout-v1',primary_summary_sha256=sha(R/'readout-v1/summary.json'),
        script_sha256=sha(Path(__file__)),rows=rows,
        inference='Operator counts and selected origins describe exposure, not causal mediation; no comparison of gains from different initial drafts, no posthoc gate or score substitution.')
    out=R/'secondary-descriptions.json'
    with out.open('x') as f:json.dump(report,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--test',action='store_true');a=p.parse_args()
    tests() if a.test else main()
