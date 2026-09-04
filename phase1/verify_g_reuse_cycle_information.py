"""Independent inverse-Laplacian verifier for G-reuse cycle information."""
import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import sys

import numpy as np

from phase1.verify_g_reuse_min_token_basis import FILES, Disjoint, checked_bytes, parse_pairs

FIELDS = ('client', 'hardware', 'time_limit', 'execution_timeout')


def groups(nodes, edges):
    disjoint = Disjoint(nodes)
    for edge in edges:
        disjoint.merge(*edge)
    output = defaultdict(set)
    for node in nodes:
        output[disjoint.root(node)].add(node)
    return list(output.values())


def inverse_kirchhoff(nodes, edges):
    ordered = sorted(nodes)
    if len(ordered) < 2:
        return 0.0
    index = {node: position for position, node in enumerate(ordered)}
    laplacian = np.zeros((len(ordered), len(ordered)), dtype=np.float64)
    for left, right in edges:
        i, j = index[left], index[right]
        laplacian[i, i] += 1.0
        laplacian[j, j] += 1.0
        laplacian[i, j] -= 1.0
        laplacian[j, i] -= 1.0
    shifted = laplacian + np.ones_like(laplacian)/len(ordered)
    inverse = np.linalg.inv(shifted)
    residual = np.max(np.abs(shifted @ inverse - np.eye(len(ordered))))
    if residual > 1e-7:
        raise ValueError('inverse_residual')
    value = float(len(ordered) * (np.trace(inverse)-1.0))
    if value < -1e-7:
        raise ValueError('negative_kirchhoff')
    return max(0.0, value)


def reconstruct(raw):
    local, global_all = parse_pairs(raw['local']), parse_pairs(raw['global'])
    grouped = json.loads(raw['cards'])
    run_of, task_of, config_of = {}, {}, {}
    for run in sorted(grouped):
        for card in grouped[run]:
            node = card['id']
            if node in run_of:
                raise ValueError('duplicate_card')
            run_of[node], task_of[node] = run, card['task']['name']
            config_of[node] = json.dumps([card.get(field) for field in FIELDS],
                                         separators=(',', ':'), allow_nan=False)
    batch_rows = [json.loads(line) for line in raw['batches'].splitlines()]
    batches = {row['run_id']: row for row in batch_rows}
    if len(batches) != len(batch_rows) or set(batches) != set(grouped):
        raise ValueError('batch_inventory')
    if json.loads(raw['manifest']).get('run_batch_manifest.jsonl') != FILES['batches'][1]:
        raise ValueError('manifest_binding')
    local_ids = set().union(*(set(edge) for edge in local))
    local_set, local_runs = set(local), {run_of[node] for node in local_ids}
    reuse = {edge for edge in global_all if set(edge) <= local_ids and edge not in local_set
             and task_of[edge[0]] == task_of[edge[1]]
             and {run_of[node] for node in edge} <= local_runs}
    full = {edge for edge in reuse if config_of[edge[0]] == config_of[edge[1]]
            and batches[run_of[edge[0]]]['source_match_status'] == 'unique'
            and batches[run_of[edge[1]]]['source_match_status'] == 'unique'}
    rows = list(csv.DictReader(io.StringIO(raw['lengths'].decode())))
    ordered = sorted(local_ids)
    if len(rows) != len(ordered):
        raise ValueError('length_coverage')
    lengths = {}
    for position, (node, row) in enumerate(zip(ordered, rows)):
        raw_tokens, valid = int(row['raw_tokens']), int(row['valid_tokens'])
        if set(row) != {'ordinal', 'raw_tokens', 'valid_tokens', 'encoding_sha256'}:
            raise ValueError('length_schema')
        if int(row['ordinal']) != position or raw_tokens <= 0 or valid != min(raw_tokens, 16384):
            raise ValueError('length_value')
        lengths[node] = valid
    forest = Disjoint(local_ids)
    for edge in local:
        forest.merge(*edge)
    basis = []
    for edge in sorted(full, key=lambda item: (lengths[item[0]]+lengths[item[1]], item)):
        if forest.merge(*edge):
            basis.append(edge)
    if (len(local), len(global_all), len(reuse), len(full), len(basis)) != (4689, 14206, 3058, 2745, 790):
        raise ValueError('known_count_drift')

    local_by, full_by, basis_by = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        local_by[task_of[edge[0]]].append(edge)
    for edge in full:
        full_by[task_of[edge[0]]].append(edge)
    for edge in basis:
        basis_by[task_of[edge[0]]].append(edge)
    task_rows = []
    for task in sorted(local_by):
        task_nodes = {node for edge in local_by[task] for node in edge}
        full_groups = groups(task_nodes, set(local_by[task]) | set(full_by[task]))
        basis_groups = groups(task_nodes, set(local_by[task]) | set(basis_by[task]))
        if sorted(sorted(group) for group in full_groups) != sorted(sorted(group) for group in basis_groups):
            raise ValueError('partition_mismatch')
        pair_count, basis_kf, full_kf, touched_count = 0, 0.0, 0.0, 0
        for group in full_groups:
            if not any(left in group and right in group for left, right in full_by[task]):
                continue
            touched_count += 1
            local_edges = [edge for edge in local_by[task] if edge[0] in group and edge[1] in group]
            full_edges = local_edges + [edge for edge in full_by[task] if edge[0] in group and edge[1] in group]
            basis_edges = local_edges + [edge for edge in basis_by[task] if edge[0] in group and edge[1] in group]
            pair_count += len(group)*(len(group)-1)//2
            basis_kf += inverse_kirchhoff(group, basis_edges)
            full_kf += inverse_kirchhoff(group, full_edges)
        if not touched_count or full_kf > basis_kf + 1e-6:
            raise ValueError('resistance_monotonicity')
        basis_average, full_average = basis_kf/pair_count, full_kf/pair_count
        task_rows.append({'nodes': len(task_nodes), 'touched_components': touched_count,
                          'pair_count': pair_count, 'local_pairs': len(local_by[task]),
                          'full_g_pairs': len(full_by[task]), 'basis_g_pairs': len(basis_by[task]),
                          'basis_kirchhoff': basis_kf, 'full_kirchhoff': full_kf,
                          'basis_average_resistance': basis_average,
                          'full_average_resistance': full_average,
                          'resistance_reduction_fraction': 1.0-full_average/basis_average})
    reductions = [row['resistance_reduction_fraction'] for row in task_rows]
    total_basis, total_full = (sum(row[key] for row in task_rows)
                               for key in ('basis_kirchhoff', 'full_kirchhoff'))
    aggregate_reduction = 1.0-total_full/total_basis
    task_rows.sort(key=lambda row: tuple(row[key] for key in
                   ('nodes', 'touched_components', 'pair_count', 'local_pairs', 'full_g_pairs',
                    'basis_g_pairs', 'basis_kirchhoff', 'full_kirchhoff',
                    'basis_average_resistance', 'full_average_resistance', 'resistance_reduction_fraction')))
    gates = {
        'aggregate_resistance_reduction_at_least_0_25': aggregate_reduction >= 0.25,
        'median_task_reduction_at_least_0_15': statistics.median(reductions) >= 0.15,
        'positive_tasks_at_least_20_of_28': sum(value > 1e-10 for value in reductions) >= 20,
        'max_equal_task_reduction_share_at_most_0_20': max(reductions)/sum(reductions) <= 0.20,
        'fixed_counts_and_partitions': len(task_rows) == 28,
    }
    return {'tasks': len(task_rows), 'full_g_pairs': len(full), 'basis_g_pairs': len(basis),
            'aggregate_basis_kirchhoff': total_basis, 'aggregate_full_kirchhoff': total_full,
            'aggregate_resistance_reduction_fraction': aggregate_reduction,
            'median_task_resistance_reduction_fraction': statistics.median(reductions),
            'positive_tasks': sum(value > 1e-10 for value in reductions),
            'max_equal_task_reduction_share': max(reductions)/sum(reductions),
            'anonymous_task_rows': task_rows, 'gates': gates, 'all_gates_pass': all(gates.values())}


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
    receipt_raw = checked_bytes(args.receipt, args.sha256, 512*1024)
    metrics = reconstruct(raw)
    payload = json.loads(receipt_raw)
    if not close(payload['metrics'], metrics):
        raise ValueError('independent_mismatch')
    expected = ('G_REUSE_CYCLES_HAVE_BROAD_SPECTRAL_INFORMATION' if metrics['all_gates_pass']
                else 'G_REUSE_CYCLE_INFORMATION_NOT_BROAD')
    if payload['status'] != expected:
        raise ValueError('status_mismatch')
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('post_hash_drift')
    return {'status': 'INDEPENDENT_G_REUSE_CYCLE_INFORMATION_CLOSE',
            'receipt_sha256': args.sha256, 'metrics': metrics, 'numpy_version': np.__version__,
            'data_open_counts': dict(opened), 'selected_edge_identities_emitted': False,
            'protected_cohort_files_opened': 0, 'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
