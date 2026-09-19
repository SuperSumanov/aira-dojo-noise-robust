"""Complete-pool quality/cost diagnostic, not an executable policy or E2E.

Cost means sum of observed per-program wall-seconds in the six-way replay,
not measured two-program wall time or charged GPU-hours. No cost/quality
conversion constant is chosen. Failures retain their elapsed time.
"""
import argparse,hashlib,itertools,json,math,statistics
from pathlib import Path


def analyze(rows):
    if len(rows)!=6 or len({r['slot'] for r in rows})!=6 or sum(r['original_selected'] for r in rows)!=2:
        raise ValueError('six unique candidates, two selected')
    if any(r['valid'] is None for r in rows):return dict(status='unknown')
    if any(type(r['wall_seconds']) not in (float,int) or not math.isfinite(r['wall_seconds']) or r['wall_seconds']<0 for r in rows):
        raise ValueError('runtime')
    if any(r['valid'] and (type(r['score']) not in (int,float) or not math.isfinite(r['score'])) for r in rows):raise ValueError('score')
    pairs=[]
    for aa,bb in itertools.combinations(rows,2):
        values=[r['score'] for r in (aa,bb) if r['valid']]
        pairs.append(dict(slots=[aa['slot'],bb['slot']],program_wall_seconds=aa['wall_seconds']+bb['wall_seconds'],
                          best_loss=min(values) if values else None,original=aa['original_selected'] and bb['original_selected']))
    chosen=next(p for p in pairs if p['original'])
    def quality(p):return p['best_loss'] if p['best_loss'] is not None else math.inf
    def dominates(a,b):
        return a['program_wall_seconds']<=b['program_wall_seconds'] and quality(a)<=quality(b) and (
            a['program_wall_seconds']<b['program_wall_seconds'] or quality(a)<quality(b))
    cheaper_better=[p['slots'] for p in pairs if dominates(p,chosen)]
    dominated=[p['slots'] for p in pairs if dominates(chosen,p)]
    uniform=statistics.mean(p['program_wall_seconds'] for p in pairs)
    if not math.isclose(uniform,sum(r['wall_seconds'] for r in rows)/3,rel_tol=1e-12):raise ValueError('independent cost identity')
    return dict(status='complete_exploratory_quality_cost_diagnostic',
        selected_pair=chosen,uniform_expected_program_wall_seconds=uniform,
        selected_to_uniform_cost_ratio=chosen['program_wall_seconds']/uniform if uniform else None,
        pairs_dominating_selected=cheaper_better,pairs_dominated_by_selected=dominated,
        selected_is_pareto_undominated=not cheaper_better,all_pairs=pairs,
        limitation='Post-execution oracle-best quality; replay per-program times with shared six-way load. No measured policy latency/GPU saving or deployable benefit.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('summary',type=Path);args=p.parse_args()
    raw=args.summary.read_bytes();data=json.loads(raw)
    result=dict(role='auxiliary_quality_cost_not_primary_endpoint',summary_sha256=hashlib.sha256(raw).hexdigest(),
        pools=[dict(seed=s,**analyze([r for r in data['rows'] if r['seed']==s])) for s in (1,2,3)])
    with args.summary.with_name('quality-cost.json').open('x') as handle:json.dump(result,handle,indent=2,allow_nan=False)
    print(json.dumps(dict(summary_sha256=result['summary_sha256'],pools=[{k:v for k,v in r.items() if k!='all_pairs'} for r in result['pools']]),indent=2))
