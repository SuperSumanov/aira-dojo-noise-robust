"""Closed18253: separate first proposal from later search, all32 retained.

Post-hoc diagnostic, not clean weight causality (original prompt gate failed).
Never substitute a later debug/valid child for the first generated proposal.
"""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from fixed_public_preview_20261014 import DONOR_PLAN_SHA, sha


def main(root,out):
    root,out=Path(root),Path(out)
    assert sha(root/'plan.json')==DONOR_PLAN_SHA and (root/'closed.json').is_file()
    plan=json.loads((root/'plan.json').read_text())
    warm=json.loads((root/'warm.private.json').read_text())
    def lines(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    perblock={b:lines(root/f'generation-{b}/events.jsonl') for b in range(4)}
    rows=[]
    for s in plan['schedule']:
        ep=root/f"episode-{s['index']}";calls=lines(ep/'effort.jsonl')
        uses=[e for e in perblock[s['block']] if e.get('run')==s['index'] and e['event']=='parent_used']
        first=uses[0] if uses else None
        c=json.loads((ep/'candidate-0.json').read_text()) if (ep/'candidate-0.json').exists() else None
        warm_hash=hashlib.sha256(warm[s['task']]['code'].encode()).hexdigest()
        matched=bool(c and first and c['code_sha256']==first['child'] and first['parent']==warm_hash and
                     calls and calls[0]['role']=='improve' and calls[0]['success'])
        valid=bool(matched and c['valid'] and c['exit_code']==0 and not c['timed_out'] and
                   c['elapsed_seconds']<=1800 and isinstance(c['score'],(int,float)) and math.isfinite(c['score']))
        initial=warm[s['task']]['metric'];sign=1 if warm[s['task']]['metric_maximize'] else -1
        # Missing/invalid proposal retains initial incumbent; does not invent a raw score.
        endpoint=max([initial]+([c['score']] if valid else []),key=lambda v:sign*v) if matched else None
        rows.append(dict(index=s['index'],task=s['task'],arm=s['arm'],seed=s['seed'],
            first_proposal_link_verified=matched,first_candidate_valid=valid,
            raw_first_score=c['score'] if valid else None,first_step_incumbent=endpoint,
            improvement_over_warm=sign*(endpoint-initial) if endpoint is not None else None,
            first_generation_seconds=calls[0]['seconds'] if calls else None,
            first_candidate_elapsed_seconds=c['elapsed_seconds'] if matched else None))
    groups=[]
    for arm in ('old_fast','old_medium','new_fast','new_medium'):
        for task in sorted(warm):
            r=[x for x in rows if (x['arm'],x['task'])==(arm,task)];assert len(r)==4
            verified=all(x['first_proposal_link_verified'] for x in r)
            groups.append(dict(arm=arm,task=task,assigned=len(r),all_links_verified=verified,
                first_valid=sum(x['first_candidate_valid'] for x in r),
                improved=sum(x['improvement_over_warm'] is not None and x['improvement_over_warm']>0 for x in r),
                first_step_incumbent_median=statistics.median(x['first_step_incumbent'] for x in r) if verified else None))
    result=dict(assigned=len(rows),links_verified=sum(x['first_proposal_link_verified'] for x in rows),
        rows=rows,groups=groups,plan_sha256=DONOR_PLAN_SHA,source_sha256=sha(__file__),
        no_candidate_text_exported=True,no_new_execution=True,original_quality_gate=False,
        original_actual_prompt_gate=False,
        limitation='Post-hoc first-proposal diagnosis only; input differences and one pool/arm remain. This does not establish a model ability or speed causal effect. Later search is NOT replaced by these scores.')
    with out.open('x') as f:json.dump(result,f,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))


if __name__=='__main__':main(*sys.argv[1:])
