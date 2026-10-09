"""Predeclared secondary pool-best endpoint; never replaces primary gates.

An improvement relative to a run's own parent need not improve the pool best.
Two tasks share a pool: four task-pool contrasts are NOT four independent units.
"""
import argparse
import datetime
import json
import math
from pathlib import Path
from lifecycle_pilot import read,write,sha

ROOT=Path('/research/d7/spc/yzyang4/scheduling-live-twochild-20261010-v1')
PLAN='082645089d69e711f55057312d49e13d0fa99bf53942e91851791c12eb1525a6'
DIRECTIONS={'random-acts-of-pizza':1,'spooky-author-identification':-1}
ARMS=('pipeline','share2')


def summarize(rows):
    if len(rows)!=16 or sorted(r['index'] for r in rows)!=list(range(16)):
        raise ValueError('retain all16 assignments')
    result=[]
    for repeat in (0,1):
        for task,sign in DIRECTIONS.items():
            own=[r for r in rows if r['repeat']==repeat and r['task']==task]
            values={};coverage={};indices={}
            for arm in ARMS:
                group=[r for r in own if r['arm']==arm]
                if len(group)!=2:raise ValueError('fixed two runs per task/arm/pool')
                valid=[]
                for r in group:
                    if r['native_valid']:
                        v=r['native_score']
                        if type(v) not in (int,float) or not math.isfinite(v) or r['native_score_verified'] is not True:
                            raise ValueError('unverified/nonfinite native endpoint')
                        if r['complete']:valid.append(v)
                coverage[arm]=len(valid);indices[arm]=[r['index'] for r in group]
                values[arm]=max(valid,key=lambda v:sign*v) if valid else None
            complete=all(coverage[a]==2 for a in ARMS)
            result.append(dict(repeat=repeat,task=task,assigned_per_arm=2,
                complete_valid_per_arm=coverage,indices=indices,
                observed_best_per_arm=values,all_four_endpoints_observed=complete,
                paired_oriented_best_difference=sign*(values['share2']-values['pipeline']) if complete else None))
    return result


def main(mode):
    if sha(ROOT/'plan.json')!=PLAN:raise ValueError('independently pinned plan')
    path=ROOT/'pool-quality-secondary-plan.json'
    if mode=='freeze':
        if any((ROOT/p).exists() for p in ('submit-intent.json','launch.json','closed.json')):
            raise ValueError('secondary endpoint must be declared before GPU submission')
        note=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            plan_sha256=PLAN,analysis_source_sha256=sha(__file__),
            endpoint='For each task in each paired pool, oriented difference in best native-selected development score among both assigned runs.',
            directions=DIRECTIONS,planned=16,paired_pool_units=2,task_pool_contrasts=4,
            missingness='Report observed best and complete-valid coverage separately; paired difference null unless all four task/arm endpoints are complete valid and externally grounded. No failure imputation.',
            primary_rule_unchanged=True,selection_rule_unchanged=True,
            reason='Closed old reexecution exposed local gain below another run incumbent; do not confuse local gain or mean gain with pool best.',
            boundary='Secondary descriptive development endpoint; two task contrasts within a pool correlated; no population significance or fresh-data confirmation.')
        write(path,note);print(json.dumps(note,sort_keys=True));return
    note=read(path)
    if note['analysis_source_sha256']!=sha(__file__):raise ValueError('secondary analysis source drift')
    if not (ROOT/'closed.json').exists():raise ValueError('only after trial closes')
    primary=ROOT/'readout-v1/runs.json'
    result=dict(secondary_plan_sha256=sha(path),primary_rows_sha256=sha(primary),
        plan_sha256=PLAN,contrasts=summarize(read(primary)),
        changes_primary_gate=False,independent_pool_pairs=2,
        boundary=note['boundary'])
    write(ROOT/'pool-quality-secondary-readout.json',result)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=('freeze','analyze'))
    main(ap.parse_args().mode)
