"""Single-action continuation comparisons; no best-of-cache oracle selection."""
import argparse
import csv
import json
import math
import os
import re
import statistics
import subprocess
from pathlib import Path
from run_comparison_reuse_20260919 import BASE, PREFIX_ERRORS, prepared, read, write, sha, setup, source_check, now
from readout_comparison_spooky_pool_20260919 import numerical


def compare(rows, prefix_matches):
    if len(rows) != 6 or sorted(r['role'] for r in rows) != ['cache'] * 4 + ['debug', 'prefix']:
        raise ValueError('complete continuation bank required')
    if any(r['valid'] is None for r in rows):
        return dict(status='UNKNOWN_NO_EFFECT_CLAIM')
    if any(type(r['valid']) is not bool or not math.isfinite(r['wall_seconds']) or r['wall_seconds'] < 0
           or (r['valid'] and (type(r['score']) not in (int, float) or not math.isfinite(r['score']))) for r in rows):
        raise ValueError('valid outcome and cost required')
    prefix = next(r for r in rows if r['role'] == 'prefix')
    if prefix['valid'] or not prefix_matches:
        return dict(status='PREFIX_NOT_REPRODUCED_NO_CONTINUATION_EFFECT')
    debug = next(r for r in rows if r['role'] == 'debug')
    cache = [r for r in rows if r['role'] == 'cache']
    def sign(a, b):
        if not a['valid'] and not b['valid']: return 0
        if not a['valid']: return -1
        if not b['valid']: return 1
        return (b['score'] > a['score']) - (b['score'] < a['score'])
    signs = [sign(r, debug) for r in cache]
    pc = sum(r['valid'] for r in cache) / 4
    ec = statistics.mean(r['wall_seconds'] for r in cache)
    eb = debug['wall_seconds']
    # First-valid stopping uses validity, never a private quality score. If the
    # cache attempt fails, retain the same fixed debug candidate in this replay.
    terminal = [r if r['valid'] else debug for r in cache]
    tsigns = [sign(r, debug) for r in terminal]
    return dict(status='COMPLETE_EXPLORATORY_CONTINUATION_BANK',
        debug_valid=debug['valid'], debug_score=debug['score'],
        cache_valid_probability=pc, cache_valid_probability_gain=pc-int(debug['valid']),
        one_action_cache_vs_debug=dict(wins=signs.count(1), ties=signs.count(0), losses=signs.count(-1), alternatives=4),
        mean_cache_execution_seconds=ec, debug_execution_seconds=eb,
        symbolic_cache_first_then_debug=dict(
            terminal_valid_probability=sum(r['valid'] for r in terminal)/4,
            terminal_quality_vs_debug=dict(wins=tsigns.count(1), ties=tsigns.count(0), losses=tsigns.count(-1)),
            expected_latency_intercept_seconds=ec+(1-pc)*eb,
            expected_latency_generation_coefficient=1-pc,
            baseline_latency_intercept_seconds=eb, baseline_latency_generation_coefficient=1,
            strict_latency_gain_if_generation_seconds_greater_than=(ec/pc-eb) if pc else None,
            expected_additional_executions=1-pc,
            caveat='Algebra on observed per-program times, not a measured live scheduler. G is fresh debug generation latency, not historical queue time. No benefit if cache validity is zero.'),
        caveat='Two exploratory runs, not independent alternatives. Debug is a recorded first response, not fresh LLM sampling. No global budget/E2E/novelty claim.')


def main(root):
    p = prepared(root)
    source_check()
    job = read(root/'launch.json')['job']
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    text = subprocess.check_output(['sacct', '-X', '-j', job, '-nP', '-o',
        'JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'], env=env, text=True, timeout=25)
    allocations = [line.split('|') for line in text.splitlines() if line.split('|')[0] == job]
    if len(allocations) != 1:
        raise ValueError('allocation identity')
    a = allocations[0]
    if a[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'} or a[3] != 'gpu28':
        raise ValueError('allocation not closed on intended hardware')
    if dict(v.split('=',1) for v in a[4].split(','))['gres/gpu'] != '6':
        raise ValueError('allocated GPU count')
    setup(root, p['commit'])
    import pandas as pd
    from dojo.tasks.mlebench.evaluate import evaluate_submission
    from mlebench.grade import validate_submission
    from mlebench.registry import registry
    comp = registry.set_data_dir(BASE/'mle-bench-data').get_competition('spooky-author-identification')
    truth, rows, bindings = None, [], {}
    for original in p['rows']:
        i = original['index']
        row = dict(original, status='not_started', valid=None, score=None, independent_score=None, wall_seconds=None)
        path = root/f'result-{i}.json'
        if path.exists():
            result = read(path)
            if any(result[k] != value for k,value in original.items()):
                raise ValueError('candidate identity drift')
            row.update(status=result['status'], wall_seconds=result['wall_seconds'])
            if result['status'] == 'returned':
                binding = read(root/f'identity-{i}.native-binding.json', result['native_binding_sha256'])
                if binding['native_identity']['job'] != job or binding['namespace']['exact_device_namespace'] is not True:
                    raise ValueError('native binding mismatch')
                bindings[i] = binding['native_identity']['selected_uuid']
                row.update(valid=False, exit_code=result['exit_code'], timed_out=result['timed_out'])
                if result['exit_code'] == 0 and not result['timed_out'] and result['submission_sha256']:
                    submission = root/f'work-{i}/submission.csv'
                    if submission.is_symlink() or sha(submission.read_bytes()) != result['submission_sha256']:
                        raise ValueError('submission changed')
                    valid, _ = validate_submission(submission, comp)
                    if valid:
                        grade, _ = evaluate_submission(submission, BASE/'mle-bench-data', 'spooky-author-identification', root/f'grade-{i}')
                        if grade is not None and math.isfinite(float(grade)):
                            if truth is None: truth = pd.read_csv(comp.answers)
                            numeric = numerical('spooky-author-identification', pd.read_csv(submission), truth)
                            if round(numeric,5) != float(grade):
                                raise ValueError('independent score mismatch')
                            row.update(valid=True, score=float(grade), independent_score=numeric)
                    if sha(submission.read_bytes()) != result['submission_sha256']:
                        raise ValueError('submission changed during grading')
        rows.append(row)
    groups = []
    for seed in (1,2):
        rr = [r for r in rows if r['seed'] == seed]
        complete = all(r['valid'] is not None for r in rr)
        if complete and len({bindings[r['index']] for r in rr}) != 6:
            raise ValueError('six unique devices for a concurrent bank')
        prefix = next(r for r in rr if r['role'] == 'prefix')
        matches = False
        if prefix['status'] == 'returned' and prefix.get('exit_code') == 1 and not prefix.get('timed_out'):
            log = root/f'output-{prefix["index"]}.private.log'
            if log.is_symlink(): raise ValueError('log symlink')
            with log.open('rb') as handle:
                handle.seek(0,2); size = handle.tell(); handle.seek(max(0,size-65536)); output = handle.read().decode(errors='replace')
            output = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', output)
            matches = output.rstrip().endswith(PREFIX_ERRORS[seed])
        groups.append(dict(seed=seed, prefix_matches=matches, **compare(rr,matches)))
    result = dict(role='exploratory_continuation_action_bank_not_live_e2e', utc=now(), job=job,
        allocation_state=a[1], allocation_seconds=int(a[2]), allocated_gpus=6, gpu_hours=int(a[2])*6/3600,
        api_calls=0, prepared_sha256=sha((root/'prepared.json').read_bytes()), rows=rows, groups=groups,
        valid=sum(r['valid'] is True for r in rows), no_valid_output=sum(r['valid'] is False for r in rows),
        unknown=sum(r['valid'] is None for r in rows))
    write(root/'summary.json',result)
    with (root/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=sorted({key for row in rows for key in row}))
        writer.writeheader();writer.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);main(p.parse_args().root)
