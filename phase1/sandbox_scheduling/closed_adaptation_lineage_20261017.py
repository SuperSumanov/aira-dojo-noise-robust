"""Closed18997: where did observed search gains come from?

Descriptive lineage of actual returned candidates. Does not delete feedback,
rerun a policy, infer independent trials, or redefine the frozen endpoint.
Only sanitized derived metadata leaves the approved DEV root.
"""
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

ROOT=Path('/research/d7/spc/yzyang4/scheduling-selective-20261017-v1')
PIN='1783555a7c680021b2a1bae874798f1042c0bfe79d0b11af70fa7f2a75d26e32'
SUMMARY='0bd972126ab1bb9427ea93e446be3d3e245955c8bd5aa7e08778b7afa05c3514'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def codehash(s):return hashlib.sha256(s.encode()).hexdigest()
def load(p,lines=False):
    b=Path(p).read_bytes()
    if SECRET.search(b):raise ValueError('credential-shaped input refused')
    return [json.loads(x) for x in b.splitlines() if x.strip()] if lines else json.loads(b)
def finite(x):return type(x) in (int,float) and math.isfinite(x)

def lineage(nodes,code,warm):
    """No numeric node outcome is used. Unknown or multiple ancestry stays unknown."""
    by_step={n['step']:n for n in nodes}
    if len(by_step)!=len(nodes):raise ValueError('duplicate journal step')
    matches=[n for n in nodes if isinstance(n.get('code'),str) and codehash(n['code'])==code]
    facts=[]
    for node in matches:
        seen=set();debug_depth=0
        while True:
            step=node['step']
            if step in seen:raise ValueError('journal cycle')
            seen.add(step)
            roles=[r for r in node.get('operators_used',[]) if r in ('draft','improve','debug','warm_start','shared_parent')]
            if len(roles)!=1:break
            role=roles[0]
            if role not in ('improve','debug'):break
            parents=node.get('parents',[])
            if len(parents)!=1 or parents[0] not in by_step:break
            parent=by_step[parents[0]]
            if role=='debug':debug_depth+=1;node=parent;continue
            if not isinstance(parent.get('code'),str):break
            origin=codehash(parent['code'])
            facts.append((debug_depth,origin==warm,origin,codehash(node['code'])))
            break
    facts=set(facts)
    if len(facts)!=1:return dict(resolved=False,matches=len(matches),category='unresolved')
    depth,is_warm,parent,proposal=facts.pop()
    return dict(resolved=True,matches=len(matches),category=('debug' if depth else 'improve')+('_from_warm' if is_warm else '_from_new'),
        debug_depth=depth,parent=parent,proposal=proposal)

def summarize(candidates,runs,groups):
    output=[]
    for group in groups:
        task,block=group['task'],group['block'];sign=-1 if task=='denoising-dirty-documents' else 1
        rr=[r for r in runs if r['task']==task and r['block']==block];assert len(rr)==4
        initial=rr[0]['initial_score'];assert all(r['initial_score']==initial for r in rr)
        cc=[c for c in candidates if c['task']==task and c['block']==block]
        assert len(cc)==sum(r['candidate_returns'] for r in rr)
        valid=[c for c in cc if c['valid']];assert len(valid)==sum(r['valid_returns'] for r in rr)
        first=[c for c in valid if c['first_attempt']]
        initial_draw_best=max([initial]+[c['score'] for c in first],key=lambda v:sign*v)
        best=max([initial]+[c['score'] for c in valid],key=lambda v:sign*v)
        assert abs(best-group['best'])<1e-12
        record=initial;increments=[]
        for c in sorted(valid,key=lambda c:(c['pool_elapsed'],c['index'],c['candidate'])):
            gain=sign*(c['score']-record)
            if gain>1e-12:
                increments.append({k:c[k] for k in ('index','candidate','category','first_attempt','pool_elapsed')}|dict(gain=gain,score=c['score']))
                record=c['score']
        output.append(dict(block=block,task=task,pool_mode=rr[0].get('pool_mode',rr[0].get('arm')),assigned=4,returned=len(cc),valid=len(valid),
            first_attempt_valid=len(first),returned_categories=dict(Counter(c['category'] for c in cc)),
            valid_categories=dict(Counter(c['category'] for c in valid)),initial=initial,first_attempt_only_observed_best=initial_draw_best,
            final_best=best,oriented_gain_after_first_attempts=sign*(best-initial_draw_best),pool_record_events=increments,
            winning_categories=sorted({c['category'] for c in valid if abs(c['score']-best)<1e-12}) if sign*(best-initial)>1e-12 else ['warm']))
    return output

def extract(root,plan_pin,summary_pin,readout,expected=32):
    """Read a pinned, already closed DEV cohort. No scoring or artifact mutation."""
    assert sha(root/'plan.json')==plan_pin and sha(root/readout/'summary.json')==summary_pin
    plan=load(root/'plan.json');summary=load(root/readout/'summary.json');runs=load(root/readout/'runs.json')
    assert expected in (32,48)
    assert load(root/'closed.json')['complete']==summary['complete']==len(runs)==expected
    assert {r['index'] for r in runs}==set(range(expected))
    assert set(r['task'] for r in runs)=={'aerial-cactus-identification','denoising-dirty-documents'}
    hashes={};warm={};used={}
    def tracked(p,lines=False):
        before=sha(p);v=load(p,lines);assert before==sha(p);hashes[str(p.relative_to(root))]=before;return v
    for block in range(expected//8):
        events=tracked(root/f'generation-{block}/events.jsonl',True)
        for e in events:
            if e['event']=='warm_start':warm[e['run']]=e['code_sha256']
            if e['event']=='parent_used':used.setdefault((e['run'],e['child']),set()).add(e['parent'])
    candidates=[]
    for r in runs:
        ep=root/f"episode-{r['index']}";nodes=tracked(ep/'checkpoint/journal.jsonl',True)
        deadline=tracked(ep/'deadline.json');slot=tracked(root/f"block-{r['block']}/budget-slot.json")
        offset=datetime.fromisoformat(deadline['started_utc']).timestamp()-slot['start'];assert 0<=offset<60
        attempted=sorted(int(p.name.split('-')[1].split('.')[0]) for p in ep.glob('candidate-*.private.json'))
        assert attempted
        for p in sorted(ep.glob('candidate-*.json')):
            if '.private.' in p.name:continue
            c=tracked(p);number=int(p.stem.split('-')[1]);assert number in attempted
            assert finite(c['elapsed_seconds']) and 0<=c['elapsed_seconds']<=plan['run_seconds']
            valid=c['valid'] is True and c['exit_code']==0 and not c['timed_out']
            if valid:assert finite(c['score'])
            fact=lineage(nodes,c['code_sha256'],warm[r['index']])
            if fact['resolved']:
                assert fact['parent'] in used.get((r['index'],fact['proposal']),set()),'journal/event parent mismatch'
            candidates.append(dict(index=r['index'],block=r['block'],task=r['task'],candidate=number,
                first_attempt=number==attempted[0],category=fact['category'],lineage_resolved=fact['resolved'],
                native_matches=fact['matches'],debug_depth=fact.get('debug_depth'),valid=valid,
                pool_elapsed=offset+c['elapsed_seconds'],score=c.get('score') if valid else None))
    groups=summarize(candidates,runs,summary['by_pool'])
    out=dict(schema=1,plan_sha256=plan_pin,summary_sha256=summary_pin,reader_sha256=sha(__file__),assigned=expected,
        candidate_receipts=len(candidates),source_hashes=hashes,candidates=candidates,groups=groups,
        limits=['Post-closure descriptive lineage, not a new policy or causal mediation estimate.',
        'First-attempt-only observed best is an observed subset, NOT a no-feedback or restart counterfactual.',
        'Debug can create quality gains; Improve from a new parent does not prove semantic use of feedback.',
        'Shared parents and repeated tasks mean trajectories are not independent treatment replications.',
        'Ambiguous or missing lineage remains unresolved; no candidate/label/prediction text exported.',
        'No primary gate changed; no GPU,model,scorer call or original artifact modification.'])
    assert sha(root/'plan.json')==plan_pin and sha(root/readout/'summary.json')==summary_pin
    return out

def main():
    out=extract(ROOT,PIN,SUMMARY,'readout-20261017-v1')
    path=ROOT/'adaptation-lineage-20261017.safe.json'
    with path.open('x') as f:json.dump(out,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps(dict(sha256=sha(path),assigned=32,candidate_receipts=out['candidate_receipts'],groups=out['groups']),sort_keys=True))

if __name__=='__main__':main()
