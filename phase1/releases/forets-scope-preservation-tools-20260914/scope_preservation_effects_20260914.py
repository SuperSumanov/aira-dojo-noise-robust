"""Fixed three-arm effects for the conditional successor, not the active trial."""
import math
import statistics

TASKS=('leaf-classification','spaceship-titanic')
SEEDS=(46,47)
ARMS=('whole_program','preserve_program','model_module')
CONTRASTS=(('whole_program','model_module'),('preserve_program','model_module'),('whole_program','preserve_program'))


def effects(rows):
    expected={(t,s,a) for t in TASKS for s in SEEDS for a in ARMS}
    if len(rows)!=12 or {(r['task'],r['seed'],r['arm']) for r in rows}!=expected:
        raise ValueError('complete twelve-row matrix required')
    table={(r['task'],r['seed'],r['arm']):r for r in rows}
    for r in rows:
        if any(type(r[k]) is not bool for k in ('technical_eligible','action_valid','iteration_valid')):
            raise ValueError('Boolean eligibility')
        for endpoint in ('action','iteration'):
            value=r[endpoint+'_score']
            if r[endpoint+'_valid']:
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('finite score')
            elif value is not None:raise ValueError('no imputation')
    groups=[];pairs=[]
    for endpoint in ('action','iteration'):
        for control,treatment in CONTRASTS:
            for task in TASKS:
                values=[]
                for seed in SEEDS:
                    left=table[task,seed,control];right=table[task,seed,treatment]
                    technical=left['technical_eligible'] and right['technical_eligible']
                    valid=technical and left[endpoint+'_valid'] and right[endpoint+'_valid']
                    gain=None
                    if valid:
                        gain=(left[endpoint+'_score']-right[endpoint+'_score']) if task==TASKS[0] else (right[endpoint+'_score']-left[endpoint+'_score'])
                        values.append(gain)
                    pairs.append(dict(endpoint=endpoint,control=control,treatment=treatment,task=task,seed=seed,
                        technical_comparable=technical,quality_comparable=valid,oriented_gain=gain,
                        treatment_minus_control_api_usd=right['api_cost_usd']-left['api_cost_usd']))
                groups.append(dict(endpoint=endpoint,control=control,treatment=treatment,task=task,planned_pairs=2,
                    quality_comparable=len(values),unknown_pairs=2-len(values),wins=sum(x>0 for x in values),
                    ties=sum(x==0 for x in values),losses=sum(x<0 for x in values),
                    median_gain=statistics.median(values) if values else None,
                    sample_std_gain=statistics.stdev(values) if len(values)>1 else None))
    return dict(pairs=pairs,groups=groups)
