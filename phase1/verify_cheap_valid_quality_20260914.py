"""Independent receipt/policy arithmetic check of the closed quality diagnostic."""
import json,statistics
from collections import defaultdict
from pathlib import Path
from analyze_cheap_recent_transfer_20260914 import read,sha,BASE
from export_cheap_transfer_20260914 import DATA,FILES
SHA='93beff6761de70a1632e4fefc09a55329b254b108a9f007f64d27b1bea37a752'
def expected(scores,values):
    ii=[i for i in range(len(scores)) if scores[i]==max(scores)]
    return sum(values[i] for i in ii)/len(ii)
def main():
    p=Path(__file__).with_name('cheap-valid-quality.json');s=read(p,SHA)
    size=read(BASE/'forets-size-only-ablation-20260914-o8h3m5qv/summary.json','67fdb9c4b3468fffb3f96e57e7374ee99c30b054e8758b4ba6b8364a7681f240')
    observed=[]
    for cohort,(suffix,hh) in DATA.items():
        old=read(BASE/('forets-wallclock-20260912-'+suffix)/FILES[0],hh[0]);selected=[r for r in old['rows'] if r['technical_eligible'] and not r['duplicate_within_run']]
        both=[r for r in selected if r['labels']==[1,1]]
        d=next(d for d in s['denominators'] if d['cohort']==cohort)
        if (d['complete_pairs'],d['both_valid_pairs'],d['both_valid_runs'])!=(len(selected),len(both),len({r['run'] for r in both})):raise ValueError('denominator')
        for r in both:
            actual=next(v for v in s['rows'] if (v['cohort'],v['run'],v['pool'])==(cohort,r['run'],r['pool']))
            sr=next(v for v in size['rows'] if (v['cohort'],v['run'],v['pool'])==(cohort,r['run'],r['pool']))
            values=[(-v if r['task']=='leaf-classification' else v) for v in actual['grades']]
            comparisons={name:expected(scores,values) for name,scores in {'full':r['scores'],'short_code':r['short_scores'],'uniform':[0,0],'size_only':sr['size_scores']}.items()}
            for name,value in comparisons.items():
                if abs(value-actual['expected_utilities'][name])>1e-12:raise ValueError('selection expectation')
            for name in ('short_code','uniform','size_only'):
                if abs(comparisons['full']-comparisons[name]-actual['full_minus_baseline'][name])>1e-12:raise ValueError('utility direction')
            observed.append(actual)
    if len(observed)!=len(s['rows']):raise ValueError('additional row')
    for group in s['groups']:
        rr=[r for r in observed if (r['cohort'],r['task'])==(group['cohort'],group['task'])];byrun=defaultdict(list)
        for r in rr:byrun[r['run']].append(r['full_minus_baseline'][group['baseline']])
        if len(rr)!=group['pairs'] or len(byrun)!=group['runs']:raise ValueError('group denominator')
        if rr:
            expected_mean=statistics.mean(statistics.mean(v) for v in byrun.values())
            if abs(expected_mean-group['run_equal_mean_gain'])>1e-12:raise ValueError('mean')
    result=dict(status='independent_denominators_selection_utility_direction_and_run_mean_verified',summary_sha256=SHA,
        pairs=len(observed),runs=len({r['run'] for r in observed}),script_sha256=sha(Path(__file__).read_bytes()),
        limitation='Numeric submission grades already independently recomputed in first worker. This checks separate aggregation, not independent execution.')
    raw=(json.dumps(result,sort_keys=True)+'\n').encode()
    with p.with_name('cheap-valid-quality-independent.json').open('xb') as f:f.write(raw)
    print(json.dumps(dict(sha256=sha(raw),**result)))
if __name__=='__main__':main()
