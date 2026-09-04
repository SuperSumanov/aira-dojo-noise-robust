"""Effective-resistance headroom of full G-reuse cycles over its token-minimum forest."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics

import numpy as np

from phase1.g_reuse_min_token_basis import LENGTHS, choose_basis, read_lengths
from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_task_breadth import derive_reuse
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project


def components(nodes, edges):
    neighbors = {node: set() for node in nodes}
    for left, right in edges:
        neighbors[left].add(right)
        neighbors[right].add(left)
    unseen, groups = set(nodes), []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack, group = [start], {start}
        while stack:
            for neighbor in sorted(neighbors[stack.pop()] & unseen):
                unseen.remove(neighbor)
                group.add(neighbor)
                stack.append(neighbor)
        groups.append(group)
    return groups


def kirchhoff(nodes, edges):
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
    eigenvalues = np.linalg.eigvalsh(laplacian)
    check(eigenvalues[0] >= -1e-8, 'negative_eigenvalue')
    positive = eigenvalues[eigenvalues > 1e-10]
    check(len(positive) == len(ordered)-1, 'component_not_connected')
    return float(len(ordered) * np.sum(1.0/positive))


def task_spectral_row(local, full, basis):
    nodes = {node for edge in local for node in edge}
    full_combined, basis_combined = set(local) | set(full), set(local) | set(basis)
    full_groups, basis_groups = components(nodes, full_combined), components(nodes, basis_combined)
    full_partition = sorted(sorted(group) for group in full_groups)
    basis_partition = sorted(sorted(group) for group in basis_groups)
    check(full_partition == basis_partition, 'partition_mismatch')
    touched = []
    full_set = set(full)
    for group in full_groups:
        if any(left in group and right in group for left, right in full_set):
            touched.append(group)
    check(touched, 'no_g_touched_component')
    pair_count, basis_kf, full_kf = 0, 0.0, 0.0
    for group in touched:
        local_edges = [edge for edge in local if edge[0] in group and edge[1] in group]
        full_edges = local_edges + [edge for edge in full if edge[0] in group and edge[1] in group]
        basis_edges = local_edges + [edge for edge in basis if edge[0] in group and edge[1] in group]
        pair_count += len(group)*(len(group)-1)//2
        basis_kf += kirchhoff(group, basis_edges)
        full_kf += kirchhoff(group, full_edges)
    check(pair_count > 0 and full_kf <= basis_kf + 1e-8, 'resistance_monotonicity')
    basis_average, full_average = basis_kf/pair_count, full_kf/pair_count
    reduction = 1.0-full_average/basis_average
    return {'nodes': len(nodes), 'touched_components': len(touched), 'pair_count': pair_count,
            'local_pairs': len(local), 'full_g_pairs': len(full), 'basis_g_pairs': len(basis),
            'basis_kirchhoff': basis_kf, 'full_kirchhoff': full_kf,
            'basis_average_resistance': basis_average, 'full_average_resistance': full_average,
            'resistance_reduction_fraction': reduction}


def calculate(local, full, basis, task_of):
    by_local, by_full, by_basis = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        by_local[task_of[edge[0]]].append(edge)
    for edge in full:
        by_full[task_of[edge[0]]].append(edge)
    for edge in basis:
        by_basis[task_of[edge[0]]].append(edge)
    identified = {task: task_spectral_row(by_local[task], by_full[task], by_basis[task])
                  for task in sorted(by_local)}
    rows = list(identified.values())
    reductions = [row['resistance_reduction_fraction'] for row in rows]
    total_basis = sum(row['basis_kirchhoff'] for row in rows)
    total_full = sum(row['full_kirchhoff'] for row in rows)
    aggregate_reduction = 1.0-total_full/total_basis
    sum_reductions = sum(reductions)
    rows.sort(key=lambda row: tuple(row.values()))
    gates = {
        'aggregate_resistance_reduction_at_least_0_25': aggregate_reduction >= 0.25,
        'median_task_reduction_at_least_0_15': statistics.median(reductions) >= 0.15,
        'positive_tasks_at_least_20_of_28': sum(value > 1e-10 for value in reductions) >= 20,
        'max_equal_task_reduction_share_at_most_0_20': max(reductions)/sum_reductions <= 0.20,
        'fixed_counts_and_partitions': len(rows) == 28 and len(full) == 2745 and len(basis) == 790,
    }
    return {'tasks': len(rows), 'full_g_pairs': len(full), 'basis_g_pairs': len(basis),
            'aggregate_basis_kirchhoff': total_basis, 'aggregate_full_kirchhoff': total_full,
            'aggregate_resistance_reduction_fraction': aggregate_reduction,
            'median_task_resistance_reduction_fraction': statistics.median(reductions),
            'positive_tasks': sum(value > 1e-10 for value in reductions),
            'max_equal_task_reduction_share': max(reductions)/sum_reductions,
            'anonymous_task_rows': rows, 'gates': gates, 'all_gates_pass': all(gates.values())}


def main():
    extras = [path for path, _ in EXTRA.values()] + [LENGTHS[0]]
    opened = install_guard(extras)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest)
    local = pairs([json.loads(line) for line in INPUTS['local'][0].read_text().splitlines()])
    global_all = pairs([json.loads(line) for line in INPUTS['global'][0].read_text().splitlines()])
    grouped = json.loads(INPUTS['cards'][0].read_text())
    run_of, task_of = project(grouped)
    cards = project_cards(grouped)
    batch_rows = [json.loads(line) for line in EXTRA['batches'][0].read_text().splitlines()]
    batches = project_batches(batch_rows)
    check(set(batches) == set(grouped), 'batch_inventory')
    check(json.loads(EXTRA['manifest'][0].read_text()).get('run_batch_manifest.jsonl') == EXTRA['batches'][1],
          'manifest_binding')
    full = record_consistent(derive_reuse(local, global_all, run_of, task_of), cards, batches)
    local_ids = {node for edge in local for node in edge}
    with LENGTHS[0].open(newline='') as handle:
        lengths = read_lengths(local_ids, list(csv.DictReader(handle)))
    basis = choose_basis(local, full, lengths)
    result = calculate(local, full, basis, task_of)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = ('G_REUSE_CYCLES_HAVE_BROAD_SPECTRAL_INFORMATION' if result['all_gates_pass']
              else 'G_REUSE_CYCLE_INFORMATION_NOT_BROAD')
    return {'status': status, 'metrics': result,
            'numpy_version': np.__version__,
            'input_sha256': {**{key: value for key, (_, value) in INPUTS.items()},
                             **{key: value for key, (_, value) in EXTRA.items()}, 'lengths': LENGTHS[1]},
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'selected_edge_identities_emitted': False, 'pool_written': False,
            'protected_cohort_files_opened': 0, 'data_open_counts': dict(opened),
            'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
