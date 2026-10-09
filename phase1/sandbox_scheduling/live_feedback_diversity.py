"""Post-closure diagnostic: timely returns versus exact-byte-distinct feedback.

Not a new success gate. Hash equality detects exact repeats only, not semantic
equivalence, independent discoveries, or final-quality improvement. No prediction
contents or private candidates are accessed or exported.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from lifecycle_pilot import read, write, sha


def summarize(candidates, horizon=600):
    if not math.isfinite(horizon) or horizon <= 0:
        raise ValueError('invalid horizon')
    timed=[]
    for c in candidates:
        t=c['elapsed_seconds']
        if not math.isfinite(t) or t < 0 or type(c['valid']) is not bool:
            raise ValueError('invalid candidate receipt')
        if t <= horizon:
            timed.append(c)
    valid=sorted((c for c in timed if c['valid']),key=lambda c:c['elapsed_seconds'])
    code=set();submission=set();code_times=[];submission_times=[]
    for c in valid:
        a=c['code_sha256'];b=c['aux']['submission_sha256'];t=c['elapsed_seconds']
        if not all(isinstance(s,str) and re.fullmatch('[0-9a-f]{64}',s) for s in (a,b)):
            raise ValueError('missing exact identity hash')
        if a not in code:code.add(a);code_times.append(t)
        if b not in submission:submission.add(b);submission_times.append(t)
    return dict(timely_returns=len(timed),valid_returns=len(valid),late_returns=len(candidates)-len(timed),
        exact_distinct_valid_codes=len(code),exact_distinct_valid_submissions=len(submission),
        repeated_valid_code_returns=len(valid)-len(code),repeated_valid_submission_returns=len(valid)-len(submission),
        first_valid_seconds=valid[0]['elapsed_seconds'] if valid else None,
        feedback_count_area_seconds=sum(horizon-c['elapsed_seconds'] for c in valid),
        distinct_code_count_area_seconds=sum(horizon-t for t in code_times),
        distinct_submission_count_area_seconds=sum(horizon-t for t in submission_times))


def main(root, output):
    root=Path(root)
    if root.name!='scheduling-live-search-20261009-v7':raise ValueError('explicit fresh dev root only')
    closed=read(root/'closed.json');plan=read(root/'plan.json')
    primary=read(root/'readout-v1/summary.json')
    if primary['plan_sha256']!=sha(root/'plan.json') or primary['closed_sha256']!=sha(root/'closed.json'):
        raise ValueError('formal readout identity mismatch')
    rows=[]
    for s in plan['schedule']:
        ep=root/f'episode-{s["index"]}'
        paths=sorted(p for p in ep.glob('candidate-*.json') if '.private.' not in p.name)
        observed=(ep/'native.json').exists() or (ep/'finished.json').exists() or bool(paths)
        rows.append(dict(**s,observed=observed,
            receipt_set_sha256=hashlib.sha256('\n'.join(sha(p) for p in paths).encode()).hexdigest(),
            counts=summarize([read(p) for p in paths],plan['run_seconds']) if observed else None))
    write(output,dict(plan_sha256=sha(root/'plan.json'),closed_sha256=sha(root/'closed.json'),
        primary_sha256=sha(root/'readout-v1/summary.json'),analysis_source_sha256=sha(__file__),rows=rows,
        boundary='Descriptive only; no replacement of frozen gates. Deduplication is within run, exact code/submission bytes, not semantic equivalence or independent exploration. Count-area units are feedback-seconds, not GPU savings. Unobserved runs remain null; failed runs are not dropped.'))
    print(json.dumps(dict(written=True,assigned=len(rows),observed=sum(r['observed'] for r in rows))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('output')
    a=p.parse_args();main(a.root,a.output)
