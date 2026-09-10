"""Read the fixed seed8/9 DEVELOPMENT matrix, never score or launch anything.

Requires a new runtime manifest after BOTH blocks have independently observed
terminal states (or an explicit not-started closeout). The manifest is supplied
by the future live adapter/collector; this reader validates its consistency, not
the authenticity of scheduler observations. Config preparation is not a runtime
manifest. No wildcard discovery and no alternate/protected data-root option.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

from forets_block_controller_20260911 import PREPARED_SHA, TREE, block_spec
from forets_e2e_readout import _final_event, _inside, _json, _process

ROOT = Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4')
ROLE = 'forets_e2e_fixed_blocks_runtime_v1'
METRICS = {'leaf-classification': ('log_loss', -1), 'spaceship-titanic': ('accuracy', 1)}
ARMS = ('uniform_random', 'critic_topk_random')
TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY', 'PREEMPTED', 'BOOT_FAIL'}
LIMIT = 2**21


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _load(path, *, digest=None):
    with path.open('rb') as stream:
        raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('oversized explicit artifact')
    if digest is not None and _hash(raw) != digest:
        raise ValueError('artifact hash mismatch')
    return _json(raw.decode('utf-8'))


def _canonical(value):
    # Unlike dict equality this distinguishes true from 1, and rejects NaNs.
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def validate_blocks(blocks):
    if not isinstance(blocks, list) or [b.get('block') for b in blocks] != [1, 2]:
        raise ValueError('both fixed blocks must have closeout records')
    allocations, result = set(), []
    for b in blocks:
        if type(b['block']) is not int:
            raise ValueError('invalid block identity')
        observed = dt.datetime.fromisoformat(b['observed_utc'])
        if observed.tzinfo is None:
            raise ValueError('closeout requires an explicit timezone')
        job = b.get('allocation_id')
        if b['state'] == 'NOT_STARTED':
            if any(b.get(k) is not None for k in ('allocation_id', 'node', 'elapsed_seconds', 'allocated_gpus', 'service_startup_seconds')):
                raise ValueError('unstarted block cannot claim allocation measurements')
            gpu_hours = None
        else:
            if b['state'] not in TERMINAL or not isinstance(job, str) or not re.fullmatch(r'[0-9]+', job):
                raise ValueError('not a terminal allocation closeout')
            if job in allocations:
                raise ValueError('allocation counted in multiple blocks')
            allocations.add(job)
            if b.get('node') not in ('gpu27', 'gpu28'):
                raise ValueError('reviewed 3090 node required')
            if type(b.get('allocated_gpus')) is not int or b['allocated_gpus'] != 2:
                raise ValueError('fixed dual-GPU allocation required')
            elapsed = b.get('elapsed_seconds')
            if elapsed is not None and not _nonnegative(elapsed):
                raise ValueError('invalid observed allocation time')
            startup = b.get('service_startup_seconds')
            if startup is not None and (not _nonnegative(startup) or (elapsed is not None and startup > elapsed)):
                raise ValueError('invalid service startup time')
            # Actual overruns are reported, not clipped to a nicer budget.
            gpu_hours = None if elapsed is None else elapsed * b['allocated_gpus'] / 3600
        result.append(dict(block=b['block'], allocation_id=job, node=b.get('node'), state=b['state'], observed_utc=b['observed_utc'],
            elapsed_seconds=b.get('elapsed_seconds'), allocated_gpus=b.get('allocated_gpus'), gpu_hours=gpu_hours,
            service_startup_seconds=b.get('service_startup_seconds'), proposed_allocation_minutes=280,
            nominal_budget_exceeded=(b.get('elapsed_seconds') > 280*60) if b.get('elapsed_seconds') is not None else None))
    return result


def validate_manifest(manifest, prepared, root):
    """Complete all metadata/path checks BEFORE reading any final result."""
    if (manifest.get('role') != ROLE or manifest.get('schema') != 1 or manifest.get('source_tree') != TREE
            or manifest.get('prepared_sha256') != PREPARED_SHA):
        raise ValueError('not this fixed development runtime manifest')
    if not re.fullmatch(r'[0-9a-f]{40}', str(manifest.get('controller_commit', ''))):
        raise ValueError('exact controller commit required')
    block_spec(prepared, 1); block_spec(prepared, 2)
    blocks = validate_blocks(manifest['blocks'])
    expected, actual = prepared['run_configs'], manifest['runs']
    if not isinstance(actual, list) or len(actual) != 8:
        raise ValueError('all eight planned slots must remain')
    paths, checked = set(), []
    for row, original in zip(actual, expected):
        if any(type(row.get(k)) != type(original[k]) or row[k] != original[k]
               for k in ('run_id', 'block', 'task', 'seed', 'arm')):
            raise ValueError('runtime matrix or order changed')
        if row['prepared_config_sha256'] != original['config_sha256']:
            raise ValueError('prepared config binding changed')
        if row['run_dir'] != 'runs/' + row['run_id']:
            raise ValueError('run directory changed')
        event = _inside(root, row['run_dir'] + '/json/eval.jsonl')
        declared = row['runtime_status']
        if declared not in ('completed', 'failed', 'cancelled', 'not_started'):
            raise ValueError('open or unknown run state in closed matrix')
        if blocks[row['block']-1]['state'] == 'NOT_STARTED' and declared != 'not_started':
            raise ValueError('attempted run in unstarted block')
        cfg_path = _inside(root, 'configs/' + row['run_id'] + '.json')
        expected_cfg = _load(cfg_path, digest=original['config_sha256'])
        if declared == 'not_started':
            if any(row.get(k) is not None for k in ('process_summary', 'runtime_config_path', 'runtime_config_sha256')):
                raise ValueError('unstarted run cannot claim runtime paths')
            process = None
        else:
            runtime_cfg_path = _inside(root, row['runtime_config_path'])
            digest = row.get('runtime_config_sha256', '')
            if not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('actual runtime config hash required')
            runtime_cfg = _load(runtime_cfg_path, digest=digest)
            if _canonical(runtime_cfg) != _canonical(expected_cfg):
                raise ValueError('runtime config differs beyond serialization')
            process = _inside(root, row['process_summary'])
            for artifact in (runtime_cfg_path, process, event):
                if artifact in paths:
                    raise ValueError('multiple runs reuse an artifact')
                paths.add(artifact)
            if process == runtime_cfg_path or process == event:
                raise ValueError('run artifacts alias')
        checked.append((row, event, process))
    return checked, blocks


def summarize(manifest, prepared, root):
    """Library entry for explicit development artifacts; no writes or discovery."""
    root = Path(root).resolve(strict=True)
    checked, blocks = validate_manifest(manifest, prepared, root)
    rows, indexed = [], {}
    for item, event, process in checked:
        if item['runtime_status'] == 'not_started':
            score, selected, issue = None, None, 'not_started'
            status, complete, elapsed, code = 'not_started', False, None, None
        else:
            # Bounded size guard before reusing the unchanged legacy parsers.
            for path in (event, process):
                if path.is_file() and path.stat().st_size > LIMIT:
                    raise ValueError('oversized explicit result')
            score, selected, issue = _final_event(event, item['task'])
            status, complete, elapsed, code = _process(process)
        eligible = item['runtime_status'] == 'completed' and complete and issue is None
        row = {k:item[k] for k in ('run_id','block','task','seed','arm','runtime_status','prepared_config_sha256')}
        row['runtime_config_sha256'] = item.get('runtime_config_sha256')
        row.update(allocation_id=blocks[item['block']-1]['allocation_id'], node=blocks[item['block']-1]['node'])
        row.update(source_tree=TREE, controller_commit=manifest['controller_commit'], metric=METRICS[item['task']][0],
            step_limit=6, execution_timeout_seconds=300, worker_wall_seconds=3540, api_attempt_cap=100,
            process_status=status, process_returncode=code, process_elapsed_seconds=elapsed,
            final_event_issue=issue, final_score_observed=score, selected_node_id=selected,
            comparable_final=eligible, comparable_score=score if eligible else None,
            api_requests_observed=None, api_cost_usd=None)
        rows.append(row); indexed[(item['task'], item['seed'], item['arm'])] = row
    pairs, tasks = [], []
    for task, (metric, direction) in METRICS.items():
        deltas = []
        for seed in (8, 9):
            random, critic = (indexed[(task, seed, arm)] for arm in ARMS)
            eligible = random['comparable_final'] and critic['comparable_final']
            delta = direction * (critic['comparable_score'] - random['comparable_score']) if eligible else None
            pairs.append(dict(task=task, seed=seed, metric=metric, comparable=eligible, improvement=delta,
                random_run_id=random['run_id'], critic_run_id=critic['run_id']))
            if eligible: deltas.append(delta)
        completion = {arm:sum(r['comparable_final'] for r in rows if r['task']==task and r['arm']==arm) for arm in ARMS}
        tasks.append(dict(task=task, metric=metric, planned_pairs=2, comparable_pairs=len(deltas),
            improvements=deltas, median_improvement=statistics.median(deltas) if deltas else None,
            sample_stdev_improvement=statistics.stdev(deltas) if len(deltas)>1 else None,
            planned_runs_per_arm=2, comparable_finals_per_arm=completion))
    known_hours = [b['gpu_hours'] for b in blocks if b['gpu_hours'] is not None]
    unmeasured = sum(b['state'] != 'NOT_STARTED' and b['gpu_hours'] is None for b in blocks)
    return dict(role=ROLE, source_tree=TREE, prepared_sha256=PREPARED_SHA,
        reader_sha256=_hash(Path(__file__).read_bytes()), python=sys.version.split()[0],
        helper_sha256={name:_hash(Path(__file__).with_name(name).read_bytes()) for name in
            ('forets_e2e_readout.py','forets_block_controller_20260911.py','forets_pilot_plan.py')},
        planned_runs=8, planned_pairs=4, comparable_pairs=sum(p['comparable'] for p in pairs),
        runs=rows, pairs=pairs, tasks=tasks, blocks=blocks,
        known_allocation_gpu_hours=sum(known_hours), unmeasured_allocated_blocks=unmeasured,
        total_allocation_gpu_hours=sum(known_hours) if unmeasured==0 else None,
        limitations=['Exploratory two-task/two-seed matrix; no confirmation or scaling claim.',
            'Conditional valid-pair differences are not all-run net utility; all slots retained.',
            'No cross-task raw-score average; unknown API usage/cost remains unknown.',
            'Allocation time includes shared service and idle time, counted once per block.',
            'Runtime/config/terminal declarations require independent collection; this reader is not a scheduler verifier.'])


def write_report(result, output):
    output = Path(output)
    output.mkdir(parents=False, exist_ok=False)
    for name in ('runs', 'pairs', 'blocks'):
        with (output / (name + '.csv')).open('x', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result[name][0]))
            writer.writeheader(); writer.writerows(result[name])
    with (output / 'summary.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-manifest', required=True, help='Explicit relative path inside the fixed new development package')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = ROOT.resolve(strict=True)
    prepared = _load(_inside(root, 'prepared.json'), digest=PREPARED_SHA)
    if Path(prepared['output']).resolve() != root:
        raise ValueError('fixed preparation location changed')
    manifest_path = _inside(root, args.runtime_manifest)
    result = summarize(_load(manifest_path), prepared, root)
    result['runtime_manifest_sha256'] = _hash(manifest_path.read_bytes())
    write_report(result, args.output)
    print(json.dumps({k:result[k] for k in ('role','planned_runs','planned_pairs','comparable_pairs')}))


if __name__ == '__main__':
    main()
