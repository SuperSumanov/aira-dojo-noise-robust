"""Closed-batch metadata diagnosis; no raw code, scores or node IDs exported."""
from collections import Counter
import hashlib
import json
from exposure_opportunity_readout import ROOT, PLAN, ORIENTATION
from lifecycle_pilot import read, sha, write
from live_readout import lines


def main():
    if sha(ROOT/'plan.json') != PLAN or not (ROOT/'closed.json').exists():
        raise ValueError('exact closed development batch required')
    out=[]
    for s in read(ROOT/'plan.json')['schedule']:
        ep=ROOT/f'episode-{s["index"]}'
        ns=[n for n in lines(ep/'checkpoint/journal.jsonl') if n.get('operators_used')]
        cs=sorted([read(p) for p in ep.glob('candidate-*.json') if '.private.' not in p.name], key=lambda c:c['elapsed_seconds'])
        nc=Counter(hashlib.sha256(n['code'].encode()).hexdigest() for n in ns if isinstance(n.get('code'),str))
        cc=Counter(c['code_sha256'] for c in cs)
        cursor=0;counts=Counter()
        for n in ns:
            if not isinstance(n.get('code'),str):counts['missing_code']+=1;continue
            pin=hashlib.sha256(n['code'].encode()).hexdigest()
            i=next((i for i in range(cursor,len(cs)) if cs[i]['code_sha256']==pin),None)
            if i is None:counts['chronological_unmatched']+=1;continue
            cursor=i+1;c=cs[i]
            if c['valid']:
                counts['valid_matched']+=1
                counts['metric_mismatch']+=n.get('metric')!=c['score']
                counts['direction_mismatch']+=n.get('metric_maximize')!=(ORIENTATION[s['task']]==1)
                counts['native_marked_buggy']+=n.get('is_buggy') is True
                counts['native_metric_null']+=n.get('metric') is None
        steps=[n['step'] for n in ns]
        out.append(dict(index=s['index'],task=s['task'],nodes=len(ns),candidates=len(cs),
            step_monotonic=steps==sorted(steps),unique_steps=len(set(steps))==len(steps),
            code_multiset_matches=sum((nc & cc).values()),duplicate_journal_codes=sum(v-1 for v in nc.values()),
            duplicate_candidate_codes=sum(v-1 for v in cc.values()),counts=dict(counts)))
    result=dict(plan_sha256=PLAN,analysis_sha256=sha(__file__),rows=out,
        boundary='Post-readout metadata diagnosis only; not a replacement readout or corrected scientific result.')
    dest=ROOT/'alignment-diagnosis-v1.json';write(dest,result)
    print(json.dumps(dict(sha256=sha(dest),**result)))


if __name__=='__main__':main()
