"""Post-closeout cost/work supplement for the fixed eight-run paid experiment.

Does not launch, fit, grade, or alter the primary frozen score reader. Candidate
payloads remain remote: export counts/times only, never programs or critic scores.
Both allocations must independently be terminal before candidate files are read.
"""
import argparse
from collections import Counter
from contextlib import closing
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import sys

ROOT = Path('/research/d7/spc/yzyang4/forets-paid-20260911-oh3np7b8')
PREPARED = '58558eed5abe1f793c77049572549c66de8c104255f8a13fa3c48e0a8b4d3593'
LIMIT = 32 * 1024 * 1024


def finite_time(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def reduce_payload(payload, *, task, arm, step):
    """No private code, selection identities or score values in the return value."""
    bind = payload['binding']
    if (payload['schema'] != 4 or bind['task'] != task
            or bind['selection_policy'] != arm or bind['step'] != step):
        raise ValueError('candidate batch binding mismatch')
    candidates = payload['candidates']
    calls = payload['task_calls']
    if not 1 <= len(candidates) <= 4:
        raise ValueError('candidate width outside fixed experiment')
    states, roles = Counter(), Counter()
    walls, interpreter_times = [], []
    timed_out = exited_zero = missing_metadata = 0
    for i, call in enumerate(calls):
        state, role = call['state'], call['intent']['role']
        if (call['call_id'] != i or state not in ('started', 'returned', 'raised', 'invalid_return')
                or role not in ('candidate', 'debug')):
            raise ValueError('unknown task call state')
        states[state] += 1
        roles[role] += 1
        wall = call['task_wall_ns']
        if wall is not None:
            if type(wall) is not int or wall < 0:
                raise ValueError('invalid task time')
            walls.append(wall / 1e9)
        meta = call['execution_metadata']
        if meta is None:
            missing_metadata += 1
        else:
            timeout = meta['timed_out_reported']
            code = meta['exit_code_reported']
            duration = meta['exec_time_reported_seconds']
            if (type(timeout) is not bool or not finite_time(duration)
                    or code is not None and type(code) is not int):
                raise ValueError('invalid interpreter receipt')
            timed_out += int(timeout)
            exited_zero += int(code == 0 and not timeout)
            interpreter_times.append(duration)
    return dict(step=step, phase=payload['phase'], pool_width=len(candidates),
        generated_candidates=sum(c['node'] is not None for c in candidates),
        candidate_task_calls=roles['candidate'], debug_task_calls=roles['debug'],
        total_task_calls=len(calls), returned_task_calls=states['returned'],
        unresolved_task_calls=states['started'], raised_task_calls=states['raised'],
        invalid_return_task_calls=states['invalid_return'], metadata_missing_calls=missing_metadata,
        interpreter_exit_zero_calls=exited_zero, interpreter_timeout_calls=timed_out,
        measured_task_calls=len(walls), task_wall_seconds_observed=math.fsum(walls),
        interpreter_seconds_observed=math.fsum(interpreter_times))


def read_batch(path, **binding):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > LIMIT:
        raise ValueError('invalid explicit candidate ledger')
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
    if len(rows) != 1:
        raise ValueError('not a single batch snapshot')
    raw, digest = rows[0]
    if hashlib.sha256(raw.encode()).hexdigest() != digest:
        raise ValueError('candidate snapshot hash mismatch')
    result = reduce_payload(json.loads(raw), **binding)
    if hashlib.sha256(path.read_bytes()).hexdigest() != before:
        raise ValueError('candidate ledger changed during read')
    result['ledger_sha256'] = before
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='New directory name under fixed root')
    a = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', a.output):
        raise ValueError('simple output directory name required')
    root = ROOT.resolve(strict=True)
    sys.path.insert(0, str(root / 'code'))
    from forets_block_collect_20260911 import collect_metadata
    from forets_block_readout_20260911 import _load, _inside
    from forets_paid_budget_20260911 import snapshot
    prepared = _load(root / 'prepared.json', digest=PREPARED)
    manifest = collect_metadata(root, prepared)  # fresh sacct BOTH blocks, no score reads
    budget_before = snapshot(root / 'paid.sqlite')
    scopes = {r['scope']: r for r in budget_before['scopes']}
    run_ids = {r['run_id'] for r in manifest['runs']}
    if set(scopes) - run_ids - {'route'}:
        raise ValueError('unexpected API scope')
    rows, batches = [], []
    for run in manifest['runs']:
        cfg = _load(root / 'configs' / (run['run_id'] + '.json'), digest=run['prepared_config_sha256'])
        checkpoint = root / run['run_dir'] / 'checkpoint'
        if cfg['solver']['checkpoint_path'] != str(checkpoint):
            raise ValueError('unexpected checkpoint location')
        leaf = _inside(root, str(checkpoint.relative_to(root)) + '/forets-candidates-private')
        entries = []
        if leaf.exists():
            for path in sorted(leaf.iterdir()):
                # A leftover lock is preserved and reported, not deleted for recovery.
                if path.name.endswith('.sqlite.lock'):
                    continue
                match = re.fullmatch(r'batch-([0-5])\.sqlite', path.name)
                if not match:
                    raise ValueError('unexpected batch artifact')
                entry = read_batch(path, task=run['task'], arm=run['arm'], step=int(match[1]))
                entry.update(run_id=run['run_id'], ledger=str(path.relative_to(root)),
                    writer_lock_remains=path.with_suffix('.sqlite.lock').exists())
                entries.append(entry)
        charge = scopes.get(run['run_id'], {})
        row = {k: run[k] for k in ('run_id', 'task', 'seed', 'arm', 'runtime_status')}
        row.update(candidate_batches=len(entries), private_ledger_directory_present=leaf.exists(),
            configured_step_limit=6, root_counts_as_step=True,
            api_calls=charge.get('calls', 0), settled_api_cost_usd=charge.get('settled_usd', 0),
            unresolved_api_calls=charge.get('unresolved', 0))
        totals = ('generated_candidates', 'candidate_task_calls', 'debug_task_calls', 'total_task_calls',
            'returned_task_calls', 'unresolved_task_calls', 'raised_task_calls', 'invalid_return_task_calls',
            'metadata_missing_calls', 'interpreter_exit_zero_calls', 'interpreter_timeout_calls',
            'measured_task_calls', 'task_wall_seconds_observed', 'interpreter_seconds_observed')
        row.update({k: sum(e[k] for e in entries) for k in totals})
        row['complete_batch_receipts'] = all(e['phase'] == 'complete' and not e['writer_lock_remains'] for e in entries)
        rows.append(row)
        batches.extend(entries)
    if snapshot(root / 'paid.sqlite') != budget_before:
        raise ValueError('campaign API ledger changed after closeout')
    result = dict(role='fixed_paid_development_cost_work_supplement', observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        source_tree=manifest['source_tree'], controller_commit=manifest['controller_commit'],
        prepared_sha256=PREPARED, measurement_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        allocation_closeout=manifest['blocks'], api_budget=budget_before, runs=rows, batches=batches,
        limitations=['Post-closeout accounting; not another performance endpoint.',
            'Returned task calls and exit zero do not establish valid final submissions.',
            'Task wall time includes task/grade work, not complete allocation or API/critic overhead.',
            'A missing ledger reports zero observed calls, not proof that nothing executed.',
            'API charges are rounded up to nano-USD per request; route charges are separate.',
            'No code, intermediate score, candidate identity or protected cohort is exported.'])
    output = root / a.output
    output.mkdir(exist_ok=False)
    with (output / 'measurements.json').open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    with (output / 'runs_cost_work.csv').open('x', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(json.dumps(dict(output=str(output), runs=len(rows), batches=len(batches),
        api_calls=budget_before['calls'], settled_usd=budget_before['settled_usd'])))


if __name__ == '__main__':
    main()
