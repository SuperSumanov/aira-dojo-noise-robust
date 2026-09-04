"""Independent grounded-Laplacian verifier for the three-point spectral frontier."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import sys

from phase1.verify_g_reuse_min_token_basis import FILES, checked_bytes
from phase1.verify_g_reuse_spectral_midpoint import IndependentTask, independent_select, prepare

FRACTIONS = (('25', 1, 4), ('50', 1, 2), ('75', 3, 4))
ARMS = ('spectral', 'cheapest', 'hash')


def point_row(local, full, basis, lengths, numerator, denominator):
    costs = {edge: lengths[edge[0]]+lengths[edge[1]] for edge in full}
    remaining = sorted(set(full)-set(basis))
    basis_tokens = sum(costs[edge] for edge in basis)
    full_tokens = sum(costs[edge] for edge in full)
    budget = ((full_tokens-basis_tokens)*numerator)//denominator
    initial = IndependentTask(local, full, basis)
    basis_kf = initial.kirchhoff()
    full_state = initial.clone()
    full_log = sum(full_state.add(edge) for edge in remaining)
    full_kf = full_state.kirchhoff()
    arms = {name: independent_select(initial.clone(), remaining, costs, budget, name) for name in ARMS}
    for result in arms.values():
        if result['additional_tokens'] > budget:
            raise ValueError('frontier_budget_exceeded')
        result['budget_utilization'] = result['additional_tokens']/budget if budget else 1.0
        result['d_capture'] = result['logdet_gain']/full_log if full_log > 1e-10 else 1.0
        headroom = basis_kf-full_kf
        result['a_capture'] = ((basis_kf-result['final_kirchhoff'])/headroom
                               if headroom > 1e-8 else 1.0)
    return {'local_pairs': len(local), 'full_g_pairs': len(full), 'basis_g_pairs': len(basis),
            'remaining_edges': len(remaining), 'basis_tokens': basis_tokens, 'full_tokens': full_tokens,
            'additional_token_budget': budget, 'basis_kirchhoff': basis_kf,
            'full_kirchhoff': full_kf, 'full_logdet_headroom': full_log, 'arms': arms}


def point_summary(rows):
    eligible = [row for row in rows if row['full_logdet_headroom'] > 1e-10]
    full_log = sum(row['full_logdet_headroom'] for row in eligible)
    a_headroom = sum(row['basis_kirchhoff']-row['full_kirchhoff'] for row in eligible)
    aggregates = {}
    for name in ARMS:
        budget = sum(row['additional_token_budget'] for row in rows)
        spent = sum(row['arms'][name]['additional_tokens'] for row in rows)
        d_gain = sum(row['arms'][name]['logdet_gain'] for row in eligible)
        a_gain = sum(row['basis_kirchhoff']-row['arms'][name]['final_kirchhoff'] for row in eligible)
        aggregates[name] = {'additional_token_budget': budget, 'additional_tokens': spent,
                            'budget_utilization': spent/budget, 'd_capture': d_gain/full_log,
                            'a_capture': a_gain/a_headroom}
    nonworse = sum(row['arms']['spectral']['d_capture']+1e-10 >=
                   max(row['arms']['cheapest']['d_capture'], row['arms']['hash']['d_capture'])
                   for row in eligible)
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(',', ':')))
    return {'eligible_cycle_tasks': len(eligible), 'aggregates': aggregates,
            'spectral_not_worse_tasks': nonworse, 'anonymous_task_rows': rows}


def reconstruct(raw):
    local, full, basis, task_of, lengths = prepare(raw)
    by_local, by_full, by_basis = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        by_local[task_of[edge[0]]].append(edge)
    for edge in full:
        by_full[task_of[edge[0]]].append(edge)
    for edge in basis:
        by_basis[task_of[edge[0]]].append(edge)
    points = {}
    for label, numerator, denominator in FRACTIONS:
        rows = [point_row(by_local[task], by_full[task], by_basis[task], lengths,
                          numerator, denominator) for task in sorted(by_local)]
        points[label] = point_summary(rows)
    means = {name: {metric: sum(points[label]['aggregates'][name][metric]
                                for label, _, _ in FRACTIONS)/3
                    for metric in ('d_capture', 'a_capture')} for name in ARMS}
    gates = {
        'all_points_within_budgets_and_spectral_utilization_at_least_0_95':
            all(result['additional_tokens'] <= row['additional_token_budget']
                for point in points.values() for row in point['anonymous_task_rows']
                for result in row['arms'].values()) and
            all(points[label]['aggregates']['spectral']['budget_utilization'] >= 0.95
                for label, _, _ in FRACTIONS),
        'spectral_d_strictly_beats_both_at_every_point':
            all(points[label]['aggregates']['spectral']['d_capture'] >
                max(points[label]['aggregates']['cheapest']['d_capture'],
                    points[label]['aggregates']['hash']['d_capture']) for label, _, _ in FRACTIONS),
        'spectral_a_strictly_beats_both_at_every_point':
            all(points[label]['aggregates']['spectral']['a_capture'] >
                max(points[label]['aggregates']['cheapest']['a_capture'],
                    points[label]['aggregates']['hash']['a_capture']) for label, _, _ in FRACTIONS),
        'spectral_mean_d_and_a_strictly_beat_both':
            means['spectral']['d_capture'] > max(means['cheapest']['d_capture'], means['hash']['d_capture']) and
            means['spectral']['a_capture'] > max(means['cheapest']['a_capture'], means['hash']['a_capture']),
        'spectral_not_worse_tasks_at_least_20_every_point':
            all(points[label]['spectral_not_worse_tasks'] >= 20 for label, _, _ in FRACTIONS),
        'all_arm_aggregate_captures_monotone':
            all(all(values[index] <= values[index+1]+1e-10 for index in range(2))
                for name in ARMS for metric in ('d_capture', 'a_capture')
                for values in [[points[label]['aggregates'][name][metric] for label, _, _ in FRACTIONS]]),
        'fixed_counts': len(by_local) == 28 and len(full) == 2745 and len(basis) == 790 and
            all(points[label]['eligible_cycle_tasks'] == 27 for label, _, _ in FRACTIONS),
    }
    return {'tasks': len(by_local), 'full_g_pairs': len(full), 'basis_g_pairs': len(basis),
            'points': points, 'equal_point_means': means, 'gates': gates,
            'all_gates_pass': all(gates.values())}


def close(left, right):
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(close(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(close(a, b) for a, b in zip(left, right))
    if isinstance(left, float) or isinstance(right, float):
        return math.isclose(float(left), float(right), rel_tol=1e-8, abs_tol=1e-7)
    return left == right


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    allowed = {path.resolve() for path, _ in FILES.values()} | {args.receipt.resolve()}
    opened = defaultdict(int)

    def guard(event, params):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise PermissionError('offline')
        if event != 'open' or not isinstance(params[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(params[0])).resolve()
        mode, flags = params[1:3]
        if ((isinstance(mode, str) and any(char in mode for char in 'wax+')) or
                (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))):
            raise PermissionError('read_only')
        if path in allowed:
            opened[str(path)] += 1
        elif path.suffix.lower() not in ('.py', '.pyc'):
            raise PermissionError('unlisted_data')

    sys.addaudithook(guard)
    raw = {name: checked_bytes(path, digest) for name, (path, digest) in FILES.items()}
    receipt = checked_bytes(args.receipt, args.sha256, 2*1024*1024)
    metrics = reconstruct(raw)
    payload = json.loads(receipt)
    if not close(payload['metrics'], metrics):
        raise ValueError('independent_mismatch')
    expected = ('G_REUSE_SPECTRAL_FRONTIER_RELATIVE_DOMINANCE_SUPPORTED' if metrics['all_gates_pass']
                else 'G_REUSE_SPECTRAL_FRONTIER_RELATIVE_DOMINANCE_NOT_SUPPORTED')
    if payload['status'] != expected:
        raise ValueError('status_mismatch')
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('post_hash_drift')
    return {'status': 'INDEPENDENT_G_REUSE_SPECTRAL_FRONTIER_CLOSE',
            'receipt_sha256': args.sha256, 'metrics': metrics,
            'data_open_counts': dict(opened), 'selected_edge_identities_emitted': False,
            'protected_cohort_files_opened': 0, 'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
