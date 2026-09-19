"""Identify unavoidable hard-pruning errors without inventing missing scores.

Retained/discarded is an ordered *decision*, not necessarily a strict numeric
critic-score inequality (ties may have been broken). Fresh observed validity
and score define quality here; this is not a claim about the historical kernel.
"""
import argparse,hashlib,itertools,json,math
from pathlib import Path


def analyze(rows):
    if len(rows)!=6 or len({r['slot'] for r in rows})!=6:raise ValueError('six unique rows')
    selected=[r for r in rows if r['original_selected']]
    other=[r for r in rows if not r['original_selected']]
    if len(selected)!=2:raise ValueError('two selected')
    if any(r['valid'] is None for r in rows):return dict(status='unknown')
    if any(type(r['valid']) is not bool or (r['valid'] and (type(r['score']) not in (int,float) or not math.isfinite(r['score']))) for r in rows):raise ValueError('valid quality')
    def better(a,b):
        if not a['valid']:return False
        return not b['valid'] or a['score']<b['score']
    possibilities=[]
    for third in other:
        retained=selected+[third];discarded=[r for r in other if r is not third]
        errors=[dict(retained_slot=a['slot'],discarded_better_slot=b['slot']) for a,b in itertools.product(retained,discarded) if better(b,a)]
        selected_valid=[r for r in selected if r['valid']]
        cutoff=max((r['score'] for r in selected_valid),default=None)
        pruned_better=[r['slot'] for r in discarded if r['valid'] and cutoff is not None and r['score']<cutoff]
        possibilities.append(dict(third_slot=third['slot'],boundary_pairs=9,strict_quality_errors=errors,
                                  pruned_valid_better_than_worst_selected_valid=pruned_better))
    return dict(status='partial_identification_from_original_selected_set',possibilities=possibilities,
        boundary_error_count_range=[min(len(p['strict_quality_errors']) for p in possibilities),max(len(p['strict_quality_errors']) for p in possibilities)],
        pruned_better_valid_count_range=[min(len(p['pruned_valid_better_than_worst_selected_valid']) for p in possibilities),max(len(p['pruned_valid_better_than_worst_selected_valid']) for p in possibilities)],
        caveat='Boundary decisions on fresh observed program outcomes, not reconstructed scores, all-pair accuracy, expected set utility or E2E effect.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);args=p.parse_args()
    raw=args.summary.read_bytes();data=json.loads(raw)
    result=dict(role='post_hoc_hard_pruning_diagnostic',summary_sha256=hashlib.sha256(raw).hexdigest(),
                pools=[dict(seed=s,**analyze([r for r in data['rows'] if r['seed']==s])) for s in (1,2,3)])
    with args.summary.with_name('pruning-loss.json').open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)
    print(json.dumps({**result,'pools':[{k:v for k,v in pool.items() if k!='possibilities'} for pool in result['pools']]},indent=2))
