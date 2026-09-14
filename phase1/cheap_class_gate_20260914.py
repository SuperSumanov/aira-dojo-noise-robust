"""One fixed class-decision gate, old complete/unknown pools, no fits."""
from collections import defaultdict
import json,statistics
from pathlib import Path
from cheap_rule_baselines_20260914 import BASE,SOURCES,read,sha,interval,distribution

def gate(scores):return [int(p>.5) for p in scores]

def main():
    size=read(BASE/'forets-size-only-ablation-20260914-o8h3m5qv/summary.json','67fdb9c4b3468fffb3f96e57e7374ee99c30b054e8758b4ba6b8364a7681f240')
    sizes={(r['cohort'],r['run'],r['pool']):r for r in size['rows']}
    rows=[];groups=[]
    for cohort,(suffix,digest) in SOURCES.items():
        source=read(BASE/('forets-wallclock-20260912-'+suffix)/'cheap-transfer-missingness.json',digest)
        for r in source['rows']:
            sr=sizes[(cohort,r['run'],r['pool'])]
            if sr['full_scores']!=r['hgb_scores']:raise ValueError('same frozen scores')
            flags=gate(r['hgb_scores']);prob=distribution(flags);ys=r['labels']
            comparisons={'full':r['hgb_scores'],'short_code':r['short_scores'],'uniform':[0,0],'size_only':sr['size_scores']}
            rr=dict(cohort=cohort,run=r['run'],task=r['task'],pool=r['pool'],source_pool_sha256=r['pool_sha256'],technical_eligible=r['technical_eligible'],
                duplicate_within_run=r['duplicate_within_run'],fully_known=r['fully_known'],labels=ys,gate_flags=flags,gate_distribution=prob.tolist(),
                changed_from_full=bool((prob!=distribution(r['hgb_scores'])).any()),validity=float(sum(p*y for p,y in zip(prob,ys))) if r['fully_known'] else None,
                comparisons={name:dict(gain_lower=interval(flags,values,ys)[0],gain_upper=interval(flags,values,ys)[1],
                    validity=float(sum(p*y for p,y in zip(distribution(values),ys))) if r['fully_known'] else None) for name,values in comparisons.items()})
            rows.append(rr)
        for task in ('leaf-classification','spaceship-titanic'):
            rr=[r for r in rows if r['cohort']==cohort and r['task']==task and r['technical_eligible'] and not r['duplicate_within_run']]
            for baseline in ('full','short_code','uniform','size_only'):
                byrun=defaultdict(list)
                for r in rr:byrun[r['run']].append(r['comparisons'][baseline])
                critical=[r for r in rr if r['fully_known'] and r['labels'][0]!=r['labels'][1]]
                groups.append(dict(cohort=cohort,task=task,baseline=baseline,runs=len(byrun),pairs=len(rr),known_discordant=len(critical),
                    gate_valid_on_discordant=sum(r['validity'] for r in critical),baseline_valid_on_discordant=sum(r['comparisons'][baseline]['validity'] for r in critical),
                    run_equal_lower=statistics.mean(statistics.mean(x['gain_lower'] for x in v) for v in byrun.values()) if byrun else None,
                    run_equal_upper=statistics.mean(statistics.mean(x['gain_upper'] for x in v) for v in byrun.values()) if byrun else None))
    quality=read(Path(__file__).with_name('cheap-valid-quality.json'),'93beff6761de70a1632e4fefc09a55329b254b108a9f007f64d27b1bea37a752');qr=[]
    for old in quality['rows']:
        r=next(r for r in rows if (r['cohort'],r['run'],r['pool'])==(old['cohort'],old['run'],old['pool']))
        utilities=[-s if old['task']=='leaf-classification' else s for s in old['grades']]
        value=sum(p*u for p,u in zip(r['gate_distribution'],utilities))
        qr.append(dict(cohort=r['cohort'],run=r['run'],task=r['task'],pool=r['pool'],gate_utility=value,
            gate_minus_baselines={name:value-v for name,v in old['expected_utilities'].items()}))
    primary=[r for r in rows if r['technical_eligible'] and not r['duplicate_within_run']];known=[r for r in primary if r['fully_known']];critical=[r for r in known if r['labels'][0]!=r['labels'][1]]
    totals={name:sum(r['comparisons'][name]['validity'] for r in known) for name in ('full','short_code','uniform','size_only')};totals['gate']=sum(r['validity'] for r in known)
    quality_gain=sum(r['gate_minus_baselines']['full'] for r in qr);changes=sum(r['changed_from_full'] for r in primary)
    result=dict(role='one_posthoc_fixed_class_gate_assay_not_deployment',threshold=.5,strict_positive=True,rows=rows,groups=groups,quality_rows=qr,
        complete_pairs=len(known),known_discordant=len(critical),gate_valid_on_discordant=sum(r['validity'] for r in critical),complete_validity_totals=totals,
        changed_pair_distributions=changes,quality_gain_sum_over_full=quality_gain,
        resource_consideration_gate=totals['gate']>=totals['short_code'] and totals['gate']>totals['uniform'] and quality_gain>=0 and changes>0,
        plan_sha256=sha(Path(__file__).with_name('CHEAP_CLASS_GATE_PLAN_20260914.md').read_bytes()),script_sha256=sha(Path(__file__).read_bytes()),
        api_calls=0,gpu_jobs=0,models_fit=0,limits='Exploratory reused closed sources, canonical threshold not calibrated; small conditional quality subset. Not an E2E result or change to current46/47 protocol.')
    raw=(json.dumps(result,sort_keys=True,allow_nan=False)+'\n').encode();p=Path(__file__).with_name('cheap-class-gate.json')
    with p.open('xb') as f:f.write(raw)
    print(json.dumps(dict(path=str(p),sha256=sha(raw),complete_pairs=len(known),known_discordant=len(critical),gate_valid_on_discordant=result['gate_valid_on_discordant'],
        complete_validity_totals=totals,changed_pair_distributions=changes,quality_gain_sum_over_full=quality_gain,quality_rows=qr,resource_consideration_gate=result['resource_consideration_gate'])))
if __name__=='__main__':main()
