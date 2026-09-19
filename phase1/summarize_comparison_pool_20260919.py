"""Per-original-run table, not treating candidate pairs as independent runs."""
import argparse,csv,hashlib,json,statistics
from pathlib import Path


def summarize(summary,bounds):
    rows=[]
    for pool in summary['pools']:
        seed=pool['seed'];b=next(x for x in bounds['pools'] if x['seed']==seed)
        if pool['status']!='COMPLETE_EXPLORATORY_POOL' or b['status']!='bounded_not_recovered_rank':
            rows.append(dict(seed=seed,status='unknown'));continue
        r=dict(seed=seed,status=pool['status'],task=next(x['task'] for x in summary['rows'] if x['seed']==seed),
               candidates=pool['candidates'],valid=pool['valid'],selected_valid=pool['selected_valid'],
               selected_best_loss=pool['selected_oracle_best'],pool_best_loss=pool['pool_oracle_best'],
               conditional_quality_gain=pool['conditional_both_pairs_valid_mean_oriented_gain'],
               retention_advantage_lower=b['ranges']['superiority_minus_inferiority'][0],
               retention_advantage_upper=b['ranges']['superiority_minus_inferiority'][1])
        r.update(pool['selected_vs_all_uniform_pairs']);rows.append(r)
    known=[r for r in rows if r['status']!='unknown']
    return rows,dict(completed_pools=len(known),unknown_pools=len(rows)-len(known),
        selected_contains_pool_best=sum(r['selected_best_loss'] is not None and r['selected_best_loss']==r['pool_best_loss'] for r in known),
        equal_pool_retention_bound=[statistics.mean(r[k] for r in known) for k in ('retention_advantage_lower','retention_advantage_upper')] if known else None,
        conditional_quality_gain_mean=statistics.mean(r['conditional_quality_gain'] for r in known if r['conditional_quality_gain'] is not None) if any(r['conditional_quality_gain'] is not None for r in known) else None,
        conditional_quality_gain_median=statistics.median(r['conditional_quality_gain'] for r in known if r['conditional_quality_gain'] is not None) if any(r['conditional_quality_gain'] is not None for r in known) else None,
        caveat='Complete pools only; no cross-task averaging, significance claim or deployable/E2E effect. Conditional quality uses different valid-pair subsets in each pool.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);args=p.parse_args()
    raw=args.summary.read_bytes();bounds=json.loads(args.summary.with_name('topk-bounds.json').read_bytes())
    if hashlib.sha256(raw).hexdigest()!=bounds['summary_sha256']:raise ValueError('bounds input identity')
    rows,aggregates=summarize(json.loads(raw),bounds)
    with args.summary.with_name('pool-summary.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({k for r in rows for k in r}));writer.writeheader();writer.writerows(rows)
    with args.summary.with_name('pool-aggregates.json').open('x') as handle:json.dump(dict(summary_sha256=bounds['summary_sha256'],**aggregates),handle,indent=2,allow_nan=False)
    print(json.dumps(aggregates,indent=2))
