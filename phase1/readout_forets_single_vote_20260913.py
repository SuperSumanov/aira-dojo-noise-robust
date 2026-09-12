"""Frozen post-closure accounting for the full single-vote development matrix."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics
from attribute_forets_wallclock_20260912 import task_partition,fee_partition
from forets_environment_build_20260912 import read,write,encode,sha

ROOT=Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-bll4ghfa')
TREE='fb2c041c8ec8e352847881ee6fe2fb56d9561aec'
PREPARED='29349e0d78ce57701db2d5eae8bc35648f1fa50165df5eaff17a6502b3e402fe'

def rank_timings(directory,expected_votes=1):
    complete=[];unfinished=[]
    for pool in sorted(directory.glob('batch-*')):
        inp=read(pool/'input.json')
        if inp['aggregation']!='single_order_rank_v1' or len(inp['orders'])!=expected_votes:
            raise ValueError('wrong actually applied vote policy')
        if not (pool/'finished.json').exists():
            unfinished.append(pool.name);continue
        finished=read(pool/'finished.json')
        n=len(inp['codes_sha256']);ranks=finished['rankings']
        if (finished['paid_calls']!=expected_votes or len(ranks)!=expected_votes or
            finished['model']!='qwen/qwen3-coder-plus' or finished['observed_task_outcomes'] is not False or
            finished['top2_order_invariant'] is not None):raise ValueError('not a completed one-vote rank')
        rank=ranks[0]
        if sorted(rank)!=list(range(n)) or any(type(i)is not int for i in rank):raise ValueError('rank permutation')
        if finished['borda']!=[float(n-rank.index(i)) for i in range(n)]:raise ValueError('single-vote scores')
        timings=finished['rank_timings']
        if len(timings)!=1 or timings[0]['order_index']!=0:raise ValueError('rank time count')
        duration=timings[0]['request_through_parse_seconds']
        if type(duration) not in (int,float) or not math.isfinite(duration) or duration<0:raise ValueError('rank time')
        if (pool/'request-1.json').exists() or (pool/'response-1.json').exists():raise ValueError('unplanned second vote')
        complete.append(dict(batch=pool.name,seconds=duration))
    return dict(completed_pools=len(complete),unfinished_pools=unfinished,
        measured_total_seconds=sum(r['seconds'] for r in complete),
        median_seconds=statistics.median(r['seconds'] for r in complete) if complete else None,
        measured_pools=complete)

def attribute(root):
    summary=read(root/'wallclock-summary.json');rows=[]
    with sqlite3.connect((root/'paid.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        for original in summary['rows']:
            rid=original['run_id'];cfg=read(root/'configs'/(rid+'.json'))
            checkpoint=Path(cfg['solver']['checkpoint_path'])
            if not checkpoint.resolve().is_relative_to(root):raise ValueError('foreign checkpoint')
            snapshots=[]
            for path in sorted((checkpoint/'forets-candidates-private').glob('batch-*.sqlite')):
                with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as ledger:
                    records=ledger.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
                if len(records)!=1 or sha(records[0][0].encode())!=records[0][1]:raise ValueError('batch hash')
                value=json.loads(records[0][0])
                if (value['binding']['task'],value['binding']['selection_policy'])!=(original['task'],original['arm']):raise ValueError('task/arm binding')
                snapshots.append(value)
            elapsed=original['worker_elapsed_seconds']
            if elapsed is None and snapshots:raise ValueError('unstarted scope has snapshots')
            timing=task_partition(snapshots,elapsed) if elapsed is not None else None
            calls=db.execute('SELECT id,cost,held,state FROM calls WHERE scope=? ORDER BY id',(rid,)).fetchall()
            fees=fee_partition(rid,calls)
            if abs(sum(x['settled_nano_usd'] for x in fees.values())/1e9-original['api_cost_usd'])>1e-9:raise ValueError('fees differ')
            ranks=rank_timings(checkpoint/'forets-contextual-judge-private')
            if original['arm']=='uniform_random' and (fees['ranking']['calls'] or ranks['completed_pools'] or ranks['unfinished_pools']):raise ValueError('control ranked candidates')
            if ranks['completed_pools']>fees['ranking']['calls']:raise ValueError('rank billing coverage')
            if elapsed is not None and ranks['measured_total_seconds']>elapsed:raise ValueError('overlapping rank clocks')
            rows.append(dict(run_id=rid,task=original['task'],seed=original['seed'],arm=original['arm'],
                valid_final=original['valid'],selected_step=original['selected_step'],timing=timing,fees=fees,ranking=ranks))
    result=dict(role='predeclared_development_cost_and_execution_mechanism_not_causal_double_vote_ablation',
        source_tree=TREE,summary_sha256=sha((root/'wallclock-summary.json').read_bytes()),rows=rows,
        limitation='Complete task-call duration includes startup/fetch/grading, not pure GPU compute. Unfinished tasks remain in remainder. Rank clocks only cover completed votes. Two-seed exploratory evidence, no significance or scaling claim.')
    write(root/'singlevote-attribution.json',encode(result));return result

def run(root):
    root=root.resolve(strict=True)
    if root!=ROOT:raise ValueError('exact frozen root only')
    read(root/'prepared.json',PREPARED)
    if read(root/'build.json')['source_tree']!=TREE:raise ValueError('source')
    files=['readout_forets_single_vote_20260913.py','readout_forets_wallclock_20260912.py',
        'readout_forets_generation_capacity_20260912.py','attribute_forets_wallclock_20260912.py']
    proofs={f:sha(Path(__file__).with_name(f).read_bytes()) for f in files}
    plan=read(root/'readout-plan.json')
    if plan['readers']!=proofs:raise ValueError('reader drift')
    write(root/'readout-intent.json',encode(dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(),readers=proofs)))
    from readout_forets_wallclock_20260912 import verify
    verify(root,seeds=(26,27),blocks=(1,2));attribute(root)
    result=dict(status='verified',utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        summary_sha256=sha((root/'wallclock-summary.json').read_bytes()),csv_sha256=sha((root/'wallclock-runs.csv').read_bytes()),
        attribution_sha256=sha((root/'singlevote-attribution.json').read_bytes()),readers=proofs)
    write(root/'readout-finished.json',encode(result));print(json.dumps(result))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();run(a.root)
