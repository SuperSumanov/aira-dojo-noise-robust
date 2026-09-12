"""Post-closeout development accounting, without extra requests or executions.

Task-call wall time includes startup, fetching and grading. Its complement is
NOT isolated critic latency. Concurrent LLM latencies must not be summed, and
file modification timestamps must not be used as request timing measurements.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3

ROOT = Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-0t4odqpn')
ROOTS = (ROOT, Path('/research/d7/spc/yzyang4/forets-wallclock-20260912-cxb9p0og'))
UNIT = 10**9


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def task_partition(snapshots, elapsed):
    if not finite(elapsed):
        raise ValueError('observed worker time required')
    phases = Counter()
    states = Counter()
    roles = Counter()
    steps = set()
    timed_ns = 0
    unfinished = 0
    generation_started = generation_returned = 0
    for data in snapshots:
        step = data['binding']['step']
        if type(step) is not int or step < 1 or step in steps or data['schema'] != 4:
            raise ValueError('duplicate or invalid batch')
        steps.add(step)
        phase = data['phase']
        if phase not in ('collecting', 'selected', 'executing', 'complete'):
            raise ValueError('unknown pool phase')
        phases[phase] += 1
        generation_started += len(data['llm_requests'])
        generation_returned += sum(c['state'] == 'returned' for c in data['llm_requests'])
        calls = data['task_calls']
        if [c['call_id'] for c in calls] != list(range(len(calls))):
            raise ValueError('task-call identity')
        for index, call in enumerate(calls):
            state = call['state']
            role = call['intent']['role']
            if state not in ('started', 'returned', 'raised', 'invalid_return') or role not in ('candidate', 'debug'):
                raise ValueError('unknown task state/role')
            states[state] += 1
            roles[role] += 1
            ns = call['task_wall_ns']
            if state == 'started':
                if ns is not None or index != len(calls)-1:
                    raise ValueError('unfinished call is not terminal')
                unfinished += 1
            else:
                if type(ns) is not int or ns < 0:
                    raise ValueError('closed call lacks measured duration')
                timed_ns += ns
    if unfinished > 1:
        raise ValueError('sequential worker has multiple unfinished calls')
    task_seconds = timed_ns / UNIT
    if task_seconds > elapsed:
        raise ValueError('task duration exceeds whole worker; do not add overlapping timings')
    return dict(batches=len(steps), batch_phases=dict(phases), task_calls=sum(states.values()),
                task_call_states=dict(states), task_call_roles=dict(roles),
                recorded_generation_requests=generation_started, returned_generation_requests=generation_returned,
                closed_task_call_seconds=task_seconds, unfinished_task_calls=unfinished,
                remainder_seconds=elapsed-task_seconds,
                remainder_kind='non_task_plus_unfinished_task' if unfinished else 'non_task',
                closed_task_call_fraction=task_seconds/elapsed if elapsed else None)


def fee_partition(run_id, calls):
    groups = {k: dict(calls=0, settled_nano_usd=0, responsibility_nano_usd=0, unresolved=0)
              for k in ('ranking', 'other')}
    seen = set()
    for ident, cost, held, state in calls:
        if ident in seen or type(held) is not int or held < 0 or state not in ('settled', 'unresolved'):
            raise ValueError('invalid or duplicate billing row')
        seen.add(ident)
        if state == 'settled':
            if type(cost) is not int or cost < 0 or cost != held:
                raise ValueError('settled cost/responsibility mismatch')
        elif cost is not None:
            raise ValueError('unresolved cost must stay unknown')
        is_rank = re.fullmatch(re.escape(run_id)+r'-context-pool-\d+-order-[01]', ident)
        group = groups['ranking' if is_rank else 'other']
        group['calls'] += 1
        group['settled_nano_usd'] += cost if cost is not None else 0
        group['responsibility_nano_usd'] += held
        group['unresolved'] += state == 'unresolved'
    return groups


def contained(path, root):
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('artifact outside explicit experiment')
    return path


def read(path, root):
    return json.loads(contained(path, root).read_bytes())


def analyze(root):
    root = root.resolve(strict=True)
    if root not in ROOTS:
        raise ValueError('only the fixed new development experiment')
    finish = read(root/'closeout-finished.json', root)
    launch = read(root/'launch.json', root)
    if finish['status'] != 'verified' or finish['job'] != launch['job']:
        raise ValueError('wait for successful independent whole-allocation readout')
    summary_raw = contained(root/'wallclock-summary.json', root).read_bytes()
    if sha(summary_raw) != finish['summary_sha256']:
        raise ValueError('closed summary hash changed')
    summary = json.loads(summary_raw)
    if summary['job'] != finish['job']:
        raise ValueError('summary allocation binding')
    if len(summary['rows']) != 8 or len({r['run_id'] for r in summary['rows']}) != 8:
        raise ValueError('all eight planned slots required')
    rows = []
    with sqlite3.connect(contained(root/'paid.sqlite', root).as_uri()+'?mode=ro', uri=True) as billing:
        for original in summary['rows']:
            rid = original['run_id']
            config = read(root/'configs'/(rid+'.json'), root)
            directory = contained(Path(config['solver']['checkpoint_path'])/'forets-candidates-private', root)
            snapshots = []
            for path in sorted(directory.glob('batch-*.sqlite')):
                with sqlite3.connect(contained(path, root).as_uri()+'?mode=ro', uri=True) as db:
                    values = db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
                if len(values) != 1 or sha(values[0][0].encode()) != values[0][1]:
                    raise ValueError('candidate snapshot hash')
                data = json.loads(values[0][0])
                if (data['binding']['task'], data['binding']['selection_policy']) != (original['task'], original['arm']):
                    raise ValueError('wrong task/arm snapshot')
                snapshots.append(data)
            elapsed = original['worker_elapsed_seconds']
            if elapsed is None and snapshots:
                raise ValueError('unstarted worker has task records')
            partition = task_partition(snapshots, elapsed) if elapsed is not None else None
            calls = billing.execute('SELECT id,cost,held,state FROM calls WHERE scope=? ORDER BY id', (rid,)).fetchall()
            fees = fee_partition(rid, calls)
            total = sum(v['settled_nano_usd'] for v in fees.values())/UNIT
            if abs(total-original['api_cost_usd']) > 1e-9:
                raise ValueError('fee decomposition differs from independent readout')
            if original['arm'] == 'uniform_random' and fees['ranking']['calls']:
                raise ValueError('random control contains critic billing')
            rows.append(dict(run_id=rid, task=original['task'], seed=original['seed'], arm=original['arm'],
                             worker_elapsed_seconds=elapsed, timing=partition, fees=fees))
    return dict(job=finish['job'], summary_sha256=finish['summary_sha256'], rows=rows,
                role='posthoc_mechanism_description_not_new_effect_test',
                reader_sha256=sha(Path(__file__).read_bytes()),
                limitation='Task-call time includes fetching/grading/startup, not pure kernel compute. Remainder includes initialization, generation, ranking, analysis and other work; an unfinished task is explicitly included when present. Ranking latency is unmeasured. No time-saving causal attribution or outcome-based selection.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    result = analyze(args.root)
    with (args.root/'wallclock-attribution.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    print(json.dumps(result, allow_nan=False))
