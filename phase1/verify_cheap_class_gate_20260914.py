"""Independent threshold, expectation, missing-label bounds and assay gate."""
import itertools,json,statistics
from collections import defaultdict
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import BASE,read,sha
from cheap_rule_baselines_20260914 import SOURCES
SHA='fafa41645ee8eeaa97eaf3aa476b19d88ab3cf7556ea914898e08fda09ab8224'
def probs(scores):
    best=max(scores);count=sum(v==best for v in scores)
    return [float(v==best)/count for v in scores]
def main():
    p=Path(__file__).with_name('cheap-class-gate.json');s=read(p,SHA)
    size=read(BASE/'forets-size-only-ablation-20260914-o8h3m5qv/summary.json','67fdb9c4b3468fffb3f96e57e7374ee99c30b054e8758b4ba6b8364a7681f240')
    sizes={(r['cohort'],r['run'],r['pool']):r for r in size['rows']};count=0
    for cohort,(suffix,h) in SOURCES.items():
        data=read(BASE/('forets-wallclock-20260912-'+suffix)/'cheap-transfer-missingness.json',h)
        for old in data['rows']:
            r=next(r for r in s['rows'] if (r['cohort'],r['run'],r['pool'])==(cohort,old['run'],old['pool']))
            flags=[int(v>.5) for v in old['hgb_scores']];ps=probs(flags)
            if r['gate_flags']!=flags or r['gate_distribution']!=ps or r['labels']!=old['labels']:raise ValueError('canonical classifier delivery')
            values={'full':old['hgb_scores'],'short_code':old['short_scores'],'uniform':[0,0],'size_only':sizes[(cohort,r['run'],r['pool'])]['size_scores']}
            for baseline,score in values.items():
                diff=[a-b for a,b in zip(ps,probs(score))]
                ends=[sum(a*y for a,y in zip(diff,ys)) for ys in itertools.product(*[(0,1) if y is None else (y,) for y in old['labels']])]
                expected=r['comparisons'][baseline]
                if abs(min(ends)-expected['gain_lower'])>1e-12 or abs(max(ends)-expected['gain_upper'])>1e-12:raise ValueError('sharp bounds')
            if r['fully_known'] and abs(sum(a*y for a,y in zip(ps,r['labels']))-r['validity'])>1e-12:raise ValueError('validity expectation')
            count+=1
    if count!=len(s['rows']):raise ValueError('matrix')
    known=[r for r in s['rows'] if r['technical_eligible'] and not r['duplicate_within_run'] and r['fully_known']]
    totals={n:sum(r['comparisons'][n]['validity'] for r in known) for n in ('full','short_code','uniform','size_only')};totals['gate']=sum(r['validity'] for r in known)
    if totals!=s['complete_validity_totals']:raise ValueError('totals')
    quality=read(p.with_name('cheap-valid-quality.json'),'93beff6761de70a1632e4fefc09a55329b254b108a9f007f64d27b1bea37a752')
    for r in s['quality_rows']:
        old=next(v for v in quality['rows'] if (v['cohort'],v['run'],v['pool'])==(r['cohort'],r['run'],r['pool']))
        gate=next(v for v in s['rows'] if (v['cohort'],v['run'],v['pool'])==(r['cohort'],r['run'],r['pool']))
        value=sum(a*y*(-1 if old['task']=='leaf-classification' else 1) for a,y in zip(gate['gate_distribution'],old['grades']))
        if abs(value-r['gate_utility'])>1e-12:raise ValueError('quality')
        for name,oldvalue in old['expected_utilities'].items():
            if abs(value-oldvalue-r['gate_minus_baselines'][name])>1e-12:raise ValueError('quality difference')
    for g in s['groups']:
        rr=[r for r in s['rows'] if (r['cohort'],r['task'])==(g['cohort'],g['task']) and r['technical_eligible'] and not r['duplicate_within_run']];runs=defaultdict(list)
        for r in rr:runs[r['run']].append(r)
        for side in ('lower','upper'):
            v=statistics.mean(statistics.mean(r['comparisons'][g['baseline']]['gain_'+side] for r in vv) for vv in runs.values()) if runs else None
            expected=g['run_equal_'+side]
            if (v is None)!=(expected is None) or (v is not None and abs(v-expected)>1e-12):raise ValueError('run aggregation')
    output=dict(status='independent_class_threshold_expectation_missingness_quality_and_aggregation_verified',summary_sha256=SHA,rows=count,
        resource_consideration_gate=s['resource_consideration_gate'],script_sha256=sha(Path(__file__).read_bytes()))
    raw=(json.dumps(output,sort_keys=True)+'\n').encode()
    with p.with_name('cheap-class-gate-independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**output)))
if __name__=='__main__':main()
