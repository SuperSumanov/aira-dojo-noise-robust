"""Join frozen judge rankings only after all programs and numerical checks close."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import closing

POOL=Path('/research/d7/spc/yzyang4/forets-current-pool-20260912-wnm9cxd0')
JUDGE=Path('/research/d7/spc/yzyang4/forets-context-judge-20260912-42qtmhgi')
TASKS=('leaf-classification','spaceship-titanic')
PLAN_SHA='08ac4d511382e78efb1a1c66e5cd4c4b12c3a92712e632068d9c15fb2f9773d9'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())


def compare(rows,ranks):
    if len(rows)!=4 or len(ranks)!=2:raise ValueError('full task and both orders required')
    if any(sorted(r)!=[0,1,2,3] or any(type(i) is not int for i in r) for r in ranks):
        raise ValueError('rank permutation')
    def score(indices):
        selected=[rows[i] for i in indices]
        values=[]
        for row in selected:
            value=row['official_score']
            if (row['status']=='valid')!=(value is not None):raise ValueError('validity mismatch')
            if value is not None:values.append(value)
        return dict(candidate_slots=len(selected),valid_candidates=len(values),
            valid_probability=len(values)/len(selected),
            conditional_mean_score=sum(values)/len(values) if values else None)
    return dict(uniform4=score(range(4)),forward_top2=score(ranks[0][:2]),reverse_top2=score(ranks[1][:2]),
        top2_order_invariant=set(ranks[0][:2])==set(ranks[1][:2]),full_order_invariant=ranks[0]==ranks[1])


def main():
    numeric=read(POOL/'independent-verification.json');original=read(POOL/'summary.json')
    finished=read(JUDGE/'finished.json');prepared=read(JUDGE/'prepared.json')
    if (numeric['job']!='13120' or numeric['verification']!='passed' or not numeric['independent_numerical_regrade']
        or not numeric['same_native_gpu'] or len(numeric['rows'])!=8 or original['job']!='13120'):
        raise ValueError('complete independent scoring required')
    if (not finished['complete'] or len(finished['requests'])!=4 or finished['result_values_opened']
        or prepared['pool_plan_sha256']!=PLAN_SHA or sha(POOL/'plan.private.json')!=PLAN_SHA):
        raise ValueError('fixed blind judge not complete')
    # Primary scores were first materialized only after the last judge call closed.
    if finished['utc']>=original['utc']:raise ValueError('judge did not close before score readout')
    all_ranks=[]
    for index in range(4):
        request=prepared['requests'][index]
        if request['index']!=index or request['task']!=TASKS[index//2] or request['display_order']!=([0,1,2,3] if index%2==0 else [3,2,1,0]):
            raise ValueError('request subset or order')
        if sha(JUDGE/f'request-{index}.private.json')!=request['request_sha256']:raise ValueError('request changed')
        receipt=finished['requests'][index]
        if receipt['status']!='ranked' or receipt['provider_confirmed']!='Alibaba':raise ValueError('request failed or wrong provider')
        raw=read(JUDGE/f'response-{index}.private.json');stored=read(JUDGE/f'ranking-{index}.private.json')
        if sha(JUDGE/f'response-{index}.private.json')!=stored['response_sha256']:raise ValueError('response changed')
        value=json.loads(raw['choices'][0]['message']['content'])
        rank=value['ranking']
        if set(value)!={'ranking'} or len(rank)!=4 or any(type(v) is not int for v in rank) or sorted(rank)!=[0,1,2,3]:
            raise ValueError('raw response permutation')
        rebuilt=[request['display_order'][r] for r in rank]
        if rebuilt!=stored['original_slot_ranking']:raise ValueError('independent order remapping mismatch')
        all_ranks.append(rebuilt)
    tables=[]
    for offset,task in enumerate(TASKS):
        rows=numeric['rows'][offset*4:offset*4+4]
        if [r['index'] for r in rows]!=list(range(offset*4,offset*4+4)) or any(r['task']!=task for r in rows):
            raise ValueError('task/index mismatch')
        table=compare(rows,all_ranks[offset*2:offset*2+2]);old=original['tasks'][offset]
        if table['uniform4']['conditional_mean_score']!=old['uniform4']['conditional_mean_score'] or table['uniform4']['valid_probability']!=old['uniform4']['valid_probability']:
            raise ValueError('baseline differs')
        tables.append(dict(task=task,metric=old['metric'],lower_is_better=old['lower_is_better'],
            existing_critic_top2=old['top2'],**table))
    with closing(sqlite3.connect((JUDGE/'paid.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        entries=db.execute("SELECT scope,cost,state,held FROM calls WHERE scope LIKE 'context-judge-%' ORDER BY scope").fetchall()
        inherited=db.execute("SELECT COUNT(*),SUM(held),SUM(COALESCE(cost,0)) FROM calls WHERE scope NOT LIKE 'context-judge-%'").fetchone()
    parent=read(JUDGE/'parent-seal.json')
    if len(entries)!=4 or [e[0] for e in entries]!=[f'context-judge-{i}' for i in range(4)] or any(e[2]!='settled' or e[1]!=e[3] for e in entries):
        raise ValueError('four settled calls required')
    if inherited!=(parent['calls'],parent['accounted_nano'],parent['settled_nano']):raise ValueError('lost parent liability')
    result=dict(role='finite_development_pool_diagnostic_not_e2e',tasks=tables,
        job='13120',allocation_gpu_hours=original['allocation_gpu_hours'],new_api_calls=4,
        new_api_settled_usd=float(Decimal(sum(e[1] for e in entries))/10**9),
        cumulative_settled_usd=finished['billing']['settled_usd'],cumulative_liability_usd=finished['billing']['accounted_usd'],
        historical_unknown_requests=finished['billing']['unresolved'],original_parent_ledger_preserved=True,
        rank_replay_independently_verified=True,judge_closed_before_primary_score_readout=True,
        controller_commit=finished['controller_commit'],pool_plan_sha256=PLAN_SHA,
        readout_script_sha256=sha(Path(__file__)),
        inputs_sha256={name:sha(path) for name,path in [('numeric',POOL/'independent-verification.json'),
            ('primary',POOL/'summary.json'),('judge_finished',JUDGE/'finished.json'),('judge_prepared',JUDGE/'prepared.json')]},
        limitations=['One generated first pool per task; repeated program slots remain.',
            'Only one execution per program; finite pool frequencies are not cross-seed estimates.',
            'Stronger model and richer context change together; this does not isolate either factor.',
            'Not an end-to-end benefit or a new-method novelty claim; no protected cohort used.'])
    with (JUDGE/'comparison.json').open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps(result))


if __name__=='__main__':main()
