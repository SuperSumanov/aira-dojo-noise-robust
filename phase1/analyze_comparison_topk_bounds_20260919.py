"""Partial identification of historical top-3, fixed before new replay grades.

Only valid if original selection really sampled two from top three of these six.
The third retained candidate is unknown, not inferred from new grades.
All four possibilities are reported. Uses post-execution best-of-two utility.
"""
import argparse,hashlib,itertools,json,math
from pathlib import Path

def bounds(rows):
    if len(rows)!=6 or len({r['slot'] for r in rows})!=6:raise ValueError('six unique candidates required')
    chosen=[r for r in rows if r['original_selected']];others=[r for r in rows if not r['original_selected']]
    if len(chosen)!=2:raise ValueError('exactly two chosen')
    if any(r['valid'] is None for r in rows):return dict(status='unknown')
    for r in rows:
        if type(r['valid']) is not bool or (r['valid'] and (type(r['score']) not in (int,float) or not math.isfinite(r['score']))):
            raise ValueError('validity/grade')
    def best(pair):return min((r['score'] for r in pair if r['valid']),default=None)
    def compare(a,b):
        if a is None:return 0 if b is None else -1
        if b is None:return 1
        return (a<b)-(a>b)
    baseline=[best(pair) for pair in itertools.combinations(rows,2)]
    baseline_valid=sum(v is not None for v in baseline)/len(baseline)
    possibilities=[]
    for third in others:
        top=chosen+[third];values=[best(pair) for pair in itertools.combinations(top,2)]
        effects=[compare(a,b) for a in values for b in baseline]
        possibilities.append(dict(unknown_third_slot=third['slot'],
            top3_any_valid_probability=sum(v is not None for v in values)/3,
            any_valid_probability_gain=sum(v is not None for v in values)/3-baseline_valid,
            superiority_minus_inferiority=sum(effects)/len(effects)))
    ranges={k:[min(p[k] for p in possibilities),max(p[k] for p in possibilities)]
            for k in ('any_valid_probability_gain','superiority_minus_inferiority')}
    lo,hi=ranges['superiority_minus_inferiority']
    return dict(status='bounded_not_recovered_rank',uniform_any_valid_probability=baseline_valid,
        possibilities=possibilities,ranges=ranges,
        conclusion=('retention_better_for_every_possible_third' if lo>0 else
                    'retention_worse_for_every_possible_third' if hi<0 else 'retention_sign_not_identified'),
        caveat='Single-pool exploration; original third unknown; post-execution best-of-two, not deployment/E2E utility.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);args=p.parse_args()
    raw=args.summary.read_bytes();data=json.loads(raw)
    result=dict(summary_sha256=hashlib.sha256(raw).hexdigest(),
        pools=[dict(seed=s,**bounds([r for r in data['rows'] if r['seed']==s])) for s in (1,2,3)])
    with args.summary.with_name('topk-bounds.json').open('x') as handle:json.dump(result,handle,indent=2)
    print(json.dumps(result,indent=2))
