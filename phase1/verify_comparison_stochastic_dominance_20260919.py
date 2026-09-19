"""Post-hoc utility-robustness check; never replaces the frozen readout.

Enumerates bit masks independently of the primary pair/top-k code. Thresholds
are the full empirical finite score support, not tuned quality cutoffs. Lower
loss is better and every valid output outranks no valid output.
"""
import argparse,hashlib,json
from decimal import Decimal
from fractions import Fraction
from pathlib import Path


def diagnose(rows):
    if len(rows)!=6 or len({r['slot'] for r in rows})!=6:raise ValueError('complete unique pool required')
    if any(r['valid'] is None for r in rows):return dict(status='unknown')
    if any(type(r['valid']) is not bool for r in rows):raise ValueError('boolean validity required')
    scores=[Decimal(str(r['score'])) if r['valid'] else None for r in rows]
    if any(s is not None and not s.is_finite() for s in scores):raise ValueError('finite scores required')
    selected=sum(1<<i for i,r in enumerate(rows) if r['original_selected'])
    if selected.bit_count()!=2:raise ValueError('two original selections')
    pairs=[m for m in range(1<<6) if m.bit_count()==2]
    retained=[m for m in range(1<<6) if m.bit_count()==3 and m&selected==selected]
    if len(pairs)!=15 or len(retained)!=4:raise ValueError('enumeration')
    def at_threshold(pair,threshold):
        return any(pair&(1<<i) and s is not None and s<=threshold for i,s in enumerate(scores))
    support=sorted(set(s for s in scores if s is not None))
    possibilities=[]
    for mask in retained:
        inner=[p for p in pairs if p&mask==p]
        cdf=[];deltas=[]
        for threshold in support:
            a=Fraction(sum(at_threshold(p,threshold) for p in inner),len(inner))
            b=Fraction(sum(at_threshold(p,threshold) for p in pairs),len(pairs))
            deltas.append(a-b)
            cdf.append(dict(loss_threshold=str(threshold),retained_cdf=str(a),uniform_cdf=str(b),difference=str(a-b)))
        possibilities.append(dict(third_slot=next(rows[i]['slot'] for i in range(6) if mask&(1<<i) and not selected&(1<<i)),
            cdf=cdf,dominates=all(d>=0 for d in deltas) and any(d>0 for d in deltas),
            dominated=all(d<=0 for d in deltas) and any(d<0 for d in deltas),
            equivalent=all(d==0 for d in deltas)))
    return dict(status='exact_finite_distribution_check',possibilities=possibilities,
                dominates_for_every_possible_third=all(x['dominates'] for x in possibilities),
                dominated_for_every_possible_third=all(x['dominated'] for x in possibilities),
                caveat='Observed fixed-pool post-execution oracle distributions only. No population, repeatability, deployed selection or E2E claim.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);args=p.parse_args()
    raw=args.summary.read_bytes();data=json.loads(raw)
    result=dict(role='post_hoc_robustness_not_a_replacement_endpoint',summary_sha256=hashlib.sha256(raw).hexdigest(),
                pools=[dict(seed=s,**diagnose([r for r in data['rows'] if r['seed']==s])) for s in (1,2,3)])
    with args.summary.with_name('stochastic-dominance.json').open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2))
