"""Independent arithmetic after both full matrices close; no regrading or tuning."""
import itertools
import json
import math
from pathlib import Path
import statistics
from forets_environment_build_20260912 import read,write,encode,sha

TASKS=('leaf-classification','spaceship-titanic');SEEDS=(42,43,44,45)
ARMS=('whole_program','model_module')
ES=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-88v5m9dr')
CLASSIC=Path('/research/d7/spc/yzyang4/forets-classic-control-20260914-6jkjkwd5')


def oriented(left,right,task):return left-right if task==TASKS[0] else right-left
def percentile(values,p):
    at=(len(values)-1)*p;lo=int(at);hi=min(lo+1,len(values)-1)
    return values[lo]*(hi-at)+values[hi]*(at-lo) if hi!=lo else values[lo]
def describe(values):
    if not values:return dict(n=0,mean=None,median=None,sample_sd=None,bootstrap_mean_95=None)
    if len(values)>4 or any(not math.isfinite(x) for x in values):raise ValueError('fixed per-task sample')
    distribution=sorted(statistics.mean(xs) for xs in itertools.product(values,repeat=len(values)))
    return dict(n=len(values),mean=statistics.mean(values),median=statistics.median(values),
        sample_sd=statistics.stdev(values) if len(values)>1 else None,
        bootstrap_mean_95=[percentile(distribution,.025),percentile(distribution,.975)],
        bootstrap='exact empirical paired-seed mean bootstrap; tiny exploratory sample, not task-population CI')


def check_rows(rows):
    expected={(t,s,a) for t in TASKS for s in SEEDS for a in ARMS}
    if len(rows)!=16 or {(r['task'],r['seed'],r['arm']) for r in rows}!=expected:raise ValueError('complete sixteen rows')
    for r in rows:
        if type(r['technical_eligible']) is not bool or type(r['action_valid']) is not bool:raise ValueError('flags')
        score=r['action_score']
        if r['action_valid']:
            if type(score) not in (int,float) or not math.isfinite(score):raise ValueError('valid finite score')
        elif score is not None:raise ValueError('missing imputed')


def scope_summary(rows):
    check_rows(rows);table={(r['task'],r['seed'],r['arm']):r for r in rows};groups=[];pairs=[]
    for task in TASKS:
        diffs=[];technical=0
        for seed in SEEDS:
            a,b=[table[task,seed,arm] for arm in ARMS]
            eligible=a['technical_eligible'] and b['technical_eligible'];technical+=eligible
            d=oriented(a['action_score'],b['action_score'],task) if eligible and a['action_valid'] and b['action_valid'] else None
            if d is not None:diffs.append(d)
            pairs.append(dict(task=task,seed=seed,technical_comparable=eligible,gain=d))
        groups.append(dict(task=task,technical_pairs=technical,wins=sum(v>0 for v in diffs),ties=sum(v==0 for v in diffs),
            losses=sum(v<0 for v in diffs),unknown_quality_pairs=4-len(diffs),**describe(diffs)))
    wins=sum(g['wins'] for g in groups);losses=sum(g['losses'] for g in groups);unknown=sum(g['unknown_quality_pairs'] for g in groups)
    practical=any(p['gain'] is not None and p['gain']>(.02 if p['task']==TASKS[0] else .005) for p in pairs)
    conditions=dict(at_least_six_technical_pairs=sum(g['technical_pairs'] for g in groups)>=6,
        at_least_three_per_task=all(g['technical_pairs']>=3 for g in groups),net_positive=wins>losses,
        each_task_has_strict_win_and_no_net_loss=all(g['wins']>=1 and g['wins']>=g['losses'] for g in groups),practical_gain=practical)
    return dict(groups=groups,pairs=pairs,conditions=conditions,original_development_gate=all(conditions.values()),
        observed_wins=wins,observed_losses=losses,unknown_pairs=unknown,
        net_win_missingness_sensitivity=[wins-losses-unknown,wins-losses+unknown],
        sensitivity_note='Sign-count bounds over unknown pairs, not score imputation or an inferential interval.')


def reference_summary(rows,classic):
    check_rows(rows)
    if len(classic)!=8 or {(r['task'],r['seed']) for r in classic}!={(t,s) for t in TASKS for s in SEEDS}:raise ValueError('complete eight reference rows')
    table={(r['task'],r['seed']):r for r in classic};groups=[];pairs=[]
    for arm in ARMS:
        for task in TASKS:
            diffs=[]
            for seed in SEEDS:
                a=table[task,seed];b=next(r for r in rows if (r['task'],r['seed'],r['arm'])==(task,seed,arm))
                eligible=a['valid'] is True and a['status']=='completed' and b['technical_eligible'] and b['action_valid']
                d=oriented(a['score'],b['action_score'],task) if eligible else None
                if d is not None:diffs.append(d)
                pairs.append(dict(arm=arm,task=task,seed=seed,agent_minus_reference_oriented=d))
            groups.append(dict(arm=arm,task=task,wins=sum(d>0 for d in diffs),ties=sum(d==0 for d in diffs),
                losses=sum(d<0 for d in diffs),unknown_pairs=4-len(diffs),**describe(diffs)))
    return dict(groups=groups,pairs=pairs,
        limitation='Matching task/seed labels, not identical random-number streams. Different search spaces/control loops and physical card/time; practical resource-cap baseline, not one-knob causal ablation.')


def main():
    closure=read(ES/'readout-finished.json')
    if closure.get('status')!='verified':raise ValueError('EScope closure')
    scope=read(ES/'edit-scope-summary.json',closure['files']['edit-scope-summary.json'])
    cc=read(CLASSIC/'readout-finished.json');classic=read(CLASSIC/'summary.json',cc['summary_sha256'])
    result=dict(scope=scope_summary(scope['rows']),classic_reference=reference_summary(scope['rows'],classic['rows']),
        source_summary_sha256=closure['files']['edit-scope-summary.json'],reference_summary_sha256=cc['summary_sha256'],
        script_sha256=sha(Path(__file__).read_bytes()),primary_endpoint='action',
        limitations='All comparisons exploratory. No raw metric pooling across tasks, tiny seed-bootstrap intervals, no new protected cohort or claimed novelty.')
    print(json.dumps(dict(sha256=write(ES/'scope-classic-independent-comparison.json',encode(result)),**result)))

if __name__=='__main__':main()
