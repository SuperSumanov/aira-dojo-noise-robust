"""Three-point relative cost-information frontier for the G-reuse spectral selector."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

from phase1.g_reuse_min_token_basis import LENGTHS, choose_basis, read_lengths
from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_spectral_midpoint import TaskGraph, select
from phase1.g_reuse_task_breadth import derive_reuse
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project

FRACTIONS = (('25', 1, 4), ('50', 1, 2), ('75', 3, 4))
ARMS = ('spectral', 'cheapest', 'hash')


def task_point(local, full, basis, lengths, numerator, denominator):
    costs = {edge: lengths[edge[0]]+lengths[edge[1]] for edge in full}
    remaining = sorted(set(full)-set(basis))
    basis_tokens = sum(costs[edge] for edge in basis)
    full_tokens = sum(costs[edge] for edge in full)
    budget = ((full_tokens-basis_tokens)*numerator)//denominator
    initial = TaskGraph(local, full, basis)
    basis_kf = initial.kirchhoff()
    full_state = initial.clone()
    full_log = sum(full_state.add(edge) for edge in remaining)
    full_kf = full_state.kirchhoff()
    arms = {name: select(initial.clone(), remaining, costs, budget, name) for name in ARMS}
    for result in arms.values():
        check(result['additional_tokens'] <= budget, 'frontier_budget_exceeded')
        result['budget_utilization'] = result['additional_tokens']/budget if budget else 1.0
        result['d_capture'] = result['logdet_gain']/full_log if full_log > 1e-10 else 1.0
        resistance_headroom = basis_kf-full_kf
        result['a_capture'] = ((basis_kf-result['final_kirchhoff'])/resistance_headroom
                               if resistance_headroom > 1e-8 else 1.0)
    return {'local_pairs': len(local), 'full_g_pairs': len(full), 'basis_g_pairs': len(basis),
            'remaining_edges': len(remaining), 'basis_tokens': basis_tokens, 'full_tokens': full_tokens,
            'additional_token_budget': budget, 'basis_kirchhoff': basis_kf,
            'full_kirchhoff': full_kf, 'full_logdet_headroom': full_log, 'arms': arms}


def summarize_point(rows):
    eligible = [row for row in rows if row['full_logdet_headroom'] > 1e-10]
    full_log = sum(row['full_logdet_headroom'] for row in eligible)
    resistance_headroom = sum(row['basis_kirchhoff']-row['full_kirchhoff'] for row in eligible)
    aggregates = {}
    for name in ARMS:
        budget = sum(row['additional_token_budget'] for row in rows)
        spent = sum(row['arms'][name]['additional_tokens'] for row in rows)
        d_gain = sum(row['arms'][name]['logdet_gain'] for row in eligible)
        a_gain = sum(row['basis_kirchhoff']-row['arms'][name]['final_kirchhoff'] for row in eligible)
        aggregates[name] = {'additional_token_budget': budget, 'additional_tokens': spent,
                            'budget_utilization': spent/budget, 'd_capture': d_gain/full_log,
                            'a_capture': a_gain/resistance_headroom}
    nonworse = sum(row['arms']['spectral']['d_capture']+1e-10 >=
                   max(row['arms']['cheapest']['d_capture'], row['arms']['hash']['d_capture'])
                   for row in eligible)
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(',', ':')))
    return {'eligible_cycle_tasks': len(eligible), 'aggregates': aggregates,
            'spectral_not_worse_tasks': nonworse, 'anonymous_task_rows': rows}


def calculate(local, full, basis, task_of, lengths):
    by_local, by_full, by_basis = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        by_local[task_of[edge[0]]].append(edge)
    for edge in full:
        by_full[task_of[edge[0]]].append(edge)
    for edge in basis:
        by_basis[task_of[edge[0]]].append(edge)
    points = {}
    for label, numerator, denominator in FRACTIONS:
        rows = [task_point(by_local[task], by_full[task], by_basis[task], lengths,
                           numerator, denominator) for task in sorted(by_local)]
        points[label] = summarize_point(rows)
    means = {name: {metric: sum(points[label]['aggregates'][name][metric]
                                for label, _, _ in FRACTIONS)/len(FRACTIONS)
                    for metric in ('d_capture', 'a_capture')} for name in ARMS}
    spectral_d = [points[label]['aggregates']['spectral']['d_capture'] for label, _, _ in FRACTIONS]
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
    result = calculate(local, full, basis, task_of, lengths)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = ('G_REUSE_SPECTRAL_FRONTIER_RELATIVE_DOMINANCE_SUPPORTED' if result['all_gates_pass']
              else 'G_REUSE_SPECTRAL_FRONTIER_RELATIVE_DOMINANCE_NOT_SUPPORTED')
    return {'status': status, 'metrics': result,
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
