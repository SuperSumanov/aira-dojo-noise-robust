"""Cost-aware effective-resistance augmentation between G-reuse basis and full graph."""
from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

import numpy as np

from phase1.g_reuse_cycle_information import components
from phase1.g_reuse_min_token_basis import LENGTHS, choose_basis, read_lengths
from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_task_breadth import derive_reuse
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project


class ResistanceState:
    def __init__(self, nodes, edges):
        self.nodes = sorted(nodes)
        self.index = {node: position for position, node in enumerate(self.nodes)}
        n = len(self.nodes)
        laplacian = np.zeros((n, n), dtype=np.float64)
        for left, right in edges:
            i, j = self.index[left], self.index[right]
            laplacian[i, i] += 1.0
            laplacian[j, j] += 1.0
            laplacian[i, j] -= 1.0
            laplacian[j, i] -= 1.0
        shifted = laplacian + np.ones_like(laplacian)/n
        self.inverse = np.linalg.inv(shifted)
        check(np.max(np.abs(shifted @ self.inverse-np.eye(n))) <= 1e-7, 'initial_inverse_residual')

    def clone(self):
        copy = object.__new__(ResistanceState)
        copy.nodes, copy.index, copy.inverse = self.nodes, self.index, self.inverse.copy()
        return copy

    def resistance(self, edge):
        i, j = self.index[edge[0]], self.index[edge[1]]
        value = float(self.inverse[i, i]+self.inverse[j, j]-2.0*self.inverse[i, j])
        check(value >= -1e-8, 'negative_effective_resistance')
        return max(0.0, value)

    def add(self, edge):
        i, j = self.index[edge[0]], self.index[edge[1]]
        direction = self.inverse[:, i]-self.inverse[:, j]
        resistance = float(direction[i]-direction[j])
        check(resistance >= -1e-8, 'negative_update_resistance')
        resistance = max(0.0, resistance)
        self.inverse -= np.outer(direction, direction)/(1.0+resistance)
        self.inverse = (self.inverse+self.inverse.T)/2.0
        return math.log1p(resistance)

    def kirchhoff(self):
        return float(len(self.nodes)*(np.trace(self.inverse)-1.0))


class TaskGraph:
    def __init__(self, local, full, basis):
        nodes = {node for edge in local for node in edge}
        final_groups = components(nodes, set(local) | set(full))
        self.states, self.node_group = [], {}
        for group in final_groups:
            if not any(left in group and right in group for left, right in full):
                continue
            initial = [edge for edge in local+basis if edge[0] in group and edge[1] in group]
            state = ResistanceState(group, initial)
            group_index = len(self.states)
            self.states.append(state)
            for node in group:
                self.node_group[node] = group_index
        check(self.states and all(edge[0] in self.node_group for edge in full), 'task_state_coverage')

    def clone(self):
        copy = object.__new__(TaskGraph)
        copy.states = [state.clone() for state in self.states]
        copy.node_group = self.node_group
        return copy

    def resistance(self, edge):
        index = self.node_group[edge[0]]
        check(self.node_group[edge[1]] == index, 'cross_component_edge')
        return self.states[index].resistance(edge)

    def add(self, edge):
        index = self.node_group[edge[0]]
        check(self.node_group[edge[1]] == index, 'cross_component_update')
        return self.states[index].add(edge)

    def kirchhoff(self):
        return sum(state.kirchhoff() for state in self.states)


def select(state, remaining, costs, budget, mode):
    available, chosen, spent, log_gain = sorted(remaining), [], 0, 0.0
    if mode == 'spectral':
        while True:
            fitting = [edge for edge in available if costs[edge] <= budget-spent]
            if not fitting:
                break
            scored = [(round(math.log1p(state.resistance(edge))/costs[edge], 15), edge)
                      for edge in fitting]
            best_score = max(value for value, _ in scored)
            edge = min(edge for value, edge in scored if value == best_score)
            available.remove(edge)
            spent += costs[edge]
            chosen.append(edge)
            log_gain += state.add(edge)
    else:
        if mode == 'cheapest':
            order = sorted(available, key=lambda edge: (costs[edge], edge))
        elif mode == 'hash':
            order = sorted(available, key=lambda edge: (hashlib.sha256(
                (edge[0]+'\0'+edge[1]).encode()).hexdigest(), edge))
        else:
            raise ValueError('unknown_selector')
        for edge in order:
            if costs[edge] > budget-spent:
                continue
            spent += costs[edge]
            chosen.append(edge)
            log_gain += state.add(edge)
    return {'additional_edges': len(chosen), 'additional_tokens': spent,
            'logdet_gain': log_gain, 'final_kirchhoff': state.kirchhoff()}


def task_row(local, full, basis, lengths):
    costs = {edge: lengths[edge[0]]+lengths[edge[1]] for edge in full}
    remaining = sorted(set(full)-set(basis))
    basis_tokens = sum(costs[edge] for edge in basis)
    full_tokens = sum(costs[edge] for edge in full)
    budget = (full_tokens-basis_tokens)//2
    base = TaskGraph(local, full, basis)
    basis_kf = base.kirchhoff()
    full_state = base.clone()
    full_log = sum(full_state.add(edge) for edge in remaining)
    full_kf = full_state.kirchhoff()
    check(full_log >= -1e-10 and full_kf <= basis_kf+1e-7, 'full_headroom_invalid')
    arms = {name: select(base.clone(), remaining, costs, budget, name)
            for name in ('spectral', 'cheapest', 'hash')}
    for result in arms.values():
        check(result['additional_tokens'] <= budget, 'budget_exceeded')
        result['budget_utilization'] = result['additional_tokens']/budget if budget else 1.0
        result['d_capture'] = result['logdet_gain']/full_log if full_log > 1e-10 else 1.0
        denominator = basis_kf-full_kf
        result['a_capture'] = (basis_kf-result['final_kirchhoff'])/denominator if denominator > 1e-8 else 1.0
    return {'local_pairs': len(local), 'full_g_pairs': len(full), 'basis_g_pairs': len(basis),
            'remaining_edges': len(remaining), 'basis_tokens': basis_tokens, 'full_tokens': full_tokens,
            'additional_token_budget': budget, 'basis_kirchhoff': basis_kf,
            'full_kirchhoff': full_kf, 'full_logdet_headroom': full_log, 'arms': arms}


def calculate(local, full, basis, task_of, lengths):
    by_local, by_full, by_basis = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        by_local[task_of[edge[0]]].append(edge)
    for edge in full:
        by_full[task_of[edge[0]]].append(edge)
    for edge in basis:
        by_basis[task_of[edge[0]]].append(edge)
    rows = [task_row(by_local[task], by_full[task], by_basis[task], lengths) for task in sorted(by_local)]
    eligible = [row for row in rows if row['full_logdet_headroom'] > 1e-10]
    full_log = sum(row['full_logdet_headroom'] for row in eligible)
    total_a = sum(row['basis_kirchhoff']-row['full_kirchhoff'] for row in eligible)
    aggregates = {}
    for name in ('spectral', 'cheapest', 'hash'):
        spent = sum(row['arms'][name]['additional_tokens'] for row in rows)
        budget = sum(row['additional_token_budget'] for row in rows)
        log_gain = sum(row['arms'][name]['logdet_gain'] for row in eligible)
        a_gain = sum(row['basis_kirchhoff']-row['arms'][name]['final_kirchhoff'] for row in eligible)
        aggregates[name] = {'additional_tokens': spent, 'additional_token_budget': budget,
                            'budget_utilization': spent/budget, 'd_capture': log_gain/full_log,
                            'a_capture': a_gain/total_a}
    spectral_captures = [row['arms']['spectral']['d_capture'] for row in eligible]
    nonworse = sum(row['arms']['spectral']['d_capture']+1e-10 >=
                   max(row['arms']['cheapest']['d_capture'], row['arms']['hash']['d_capture'])
                   for row in eligible)
    gates = {
        'all_arms_within_task_budgets_and_spectral_utilization_at_least_0_95':
            all(result['additional_tokens'] <= row['additional_token_budget']
                for row in rows for result in row['arms'].values()) and
            aggregates['spectral']['budget_utilization'] >= 0.95,
        'spectral_aggregate_d_capture_at_least_0_75': aggregates['spectral']['d_capture'] >= 0.75,
        'spectral_aggregate_d_strictly_beats_both': aggregates['spectral']['d_capture'] >
            max(aggregates['cheapest']['d_capture'], aggregates['hash']['d_capture']),
        'spectral_aggregate_a_strictly_beats_both': aggregates['spectral']['a_capture'] >
            max(aggregates['cheapest']['a_capture'], aggregates['hash']['a_capture']),
        'spectral_task_d_not_worse_than_both_at_least_20': nonworse >= 20,
        'spectral_median_task_d_capture_at_least_0_70': statistics.median(spectral_captures) >= 0.70,
        'fixed_counts': len(rows) == 28 and len(full) == 2745 and len(basis) == 790,
    }
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(',', ':')))
    return {'tasks': len(rows), 'eligible_cycle_tasks': len(eligible), 'full_g_pairs': len(full),
            'basis_g_pairs': len(basis), 'aggregates': aggregates,
            'spectral_not_worse_tasks': nonworse,
            'spectral_median_task_d_capture': statistics.median(spectral_captures),
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
    full = record_consistent(derive_reuse(local, global_all, run_of, task_of), cards, batches)
    local_ids = {node for edge in local for node in edge}
    with LENGTHS[0].open(newline='') as handle:
        lengths = read_lengths(local_ids, list(csv.DictReader(handle)))
    basis = choose_basis(local, full, lengths)
    result = calculate(local, full, basis, task_of, lengths)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = ('G_REUSE_SPECTRAL_MIDPOINT_STRUCTURALLY_SUPPORTED' if result['all_gates_pass']
              else 'G_REUSE_SPECTRAL_MIDPOINT_NOT_SUPPORTED')
    return {'status': status, 'metrics': result, 'numpy_version': np.__version__,
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
