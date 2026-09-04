"""Independent grounded-Laplacian verifier for the spectral midpoint selector."""
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


class GroundedState:
    def __init__(self, nodes, edges):
        self.nodes = sorted(nodes)
        self.anchor = self.nodes[-1]
        self.index = {node: position for position, node in enumerate(self.nodes[:-1])}
        n = len(self.nodes)
        reduced = np.zeros((n-1, n-1), dtype=np.float64)
        for left, right in edges:
            vector = self.vector((left, right))
            reduced += np.outer(vector, vector)
        self.inverse = np.linalg.inv(reduced)
        if np.max(np.abs(reduced @ self.inverse-np.eye(n-1))) > 1e-7:
            raise ValueError('grounded_inverse_residual')

    def vector(self, edge):
        vector = np.zeros(len(self.nodes)-1, dtype=np.float64)
        if edge[0] != self.anchor:
            vector[self.index[edge[0]]] += 1.0
        if edge[1] != self.anchor:
            vector[self.index[edge[1]]] -= 1.0
        return vector

    def clone(self):
        copy = object.__new__(GroundedState)
        copy.nodes, copy.anchor, copy.index = self.nodes, self.anchor, self.index
        copy.inverse = self.inverse.copy()
        return copy

    def resistance(self, edge):
        vector = self.vector(edge)
        value = float(vector @ self.inverse @ vector)
        if value < -1e-8:
            raise ValueError('negative_grounded_resistance')
        return max(0.0, value)

    def add(self, edge):
        vector = self.vector(edge)
        transformed = self.inverse @ vector
        resistance = float(vector @ transformed)
        if resistance < -1e-8:
            raise ValueError('negative_grounded_update')
        resistance = max(0.0, resistance)
        self.inverse -= np.outer(transformed, transformed)/(1.0+resistance)
        self.inverse = (self.inverse+self.inverse.T)/2.0
        return math.log1p(resistance)

    def kirchhoff(self):
        n = len(self.nodes)
        return float(n*np.trace(self.inverse)-np.sum(self.inverse))


class IndependentTask:
    def __init__(self, local, full, basis):
        nodes = {node for edge in local for node in edge}
        disjoint = Disjoint(nodes)
        for edge in set(local) | set(full):
            disjoint.merge(*edge)
        grouped = defaultdict(set)
        for node in nodes:
            grouped[disjoint.root(node)].add(node)
        self.states, self.node_group = [], {}
        for group in grouped.values():
            if not any(left in group and right in group for left, right in full):
                continue
            initial = [edge for edge in local+basis if edge[0] in group and edge[1] in group]
            state = GroundedState(group, initial)
            position = len(self.states)
            self.states.append(state)
            for node in group:
                self.node_group[node] = position
        if not self.states or not all(edge[0] in self.node_group for edge in full):
            raise ValueError('independent_task_coverage')

    def clone(self):
        copy = object.__new__(IndependentTask)
        copy.states = [state.clone() for state in self.states]
        copy.node_group = self.node_group
        return copy

    def resistance(self, edge):
        position = self.node_group[edge[0]]
        if self.node_group[edge[1]] != position:
            raise ValueError('independent_cross_component')
        return self.states[position].resistance(edge)

    def add(self, edge):
        position = self.node_group[edge[0]]
        if self.node_group[edge[1]] != position:
            raise ValueError('independent_cross_component_update')
        return self.states[position].add(edge)

    def kirchhoff(self):
        return sum(state.kirchhoff() for state in self.states)


def independent_select(state, remaining, costs, budget, mode):
    available, chosen, spent, log_gain = sorted(remaining), [], 0, 0.0
    if mode == 'spectral':
        while True:
            fitting = [edge for edge in available if costs[edge] <= budget-spent]
            if not fitting:
                break
            scored = [(round(math.log1p(state.resistance(edge))/costs[edge], 15), edge)
                      for edge in fitting]
            maximum = max(score for score, _ in scored)
            edge = min(edge for score, edge in scored if score == maximum)
            available.remove(edge)
            spent += costs[edge]
            chosen.append(edge)
            log_gain += state.add(edge)
    else:
        if mode == 'cheapest':
            ordered = sorted(available, key=lambda edge: (costs[edge], edge))
        elif mode == 'hash':
            ordered = sorted(available, key=lambda edge: (hashlib.sha256(
                (edge[0]+'\0'+edge[1]).encode()).hexdigest(), edge))
        else:
            raise ValueError('independent_unknown_selector')
        for edge in ordered:
            if costs[edge] <= budget-spent:
                spent += costs[edge]
                chosen.append(edge)
                log_gain += state.add(edge)
    return {'additional_edges': len(chosen), 'additional_tokens': spent,
            'logdet_gain': log_gain, 'final_kirchhoff': state.kirchhoff()}


def prepare(raw):
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
    local_ids, local_set = set().union(*(set(edge) for edge in local)), set(local)
    local_runs = {run_of[node] for node in local_ids}
    reuse = {edge for edge in global_all if set(edge) <= local_ids and edge not in local_set
             and task_of[edge[0]] == task_of[edge[1]]
             and {run_of[node] for node in edge} <= local_runs}
    full = {edge for edge in reuse if config_of[edge[0]] == config_of[edge[1]]
            and batches[run_of[edge[0]]]['source_match_status'] == 'unique'
            and batches[run_of[edge[1]]]['source_match_status'] == 'unique'}
    length_rows = list(csv.DictReader(io.StringIO(raw['lengths'].decode())))
    ordered_ids = sorted(local_ids)
    if len(length_rows) != len(ordered_ids):
        raise ValueError('length_coverage')
    lengths = {}
    for position, (node, row) in enumerate(zip(ordered_ids, length_rows)):
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
    return local, list(full), basis, task_of, lengths


def reconstruct(raw):
    local, full, basis, task_of, lengths = prepare(raw)
    local_by, full_by, basis_by = defaultdict(list), defaultdict(list), defaultdict(list)
    for edge in local:
        local_by[task_of[edge[0]]].append(edge)
    for edge in full:
        full_by[task_of[edge[0]]].append(edge)
    for edge in basis:
        basis_by[task_of[edge[0]]].append(edge)
    rows = []
    for task in sorted(local_by):
        task_local, task_full, task_basis = local_by[task], full_by[task], basis_by[task]
        costs = {edge: lengths[edge[0]]+lengths[edge[1]] for edge in task_full}
        remaining = sorted(set(task_full)-set(task_basis))
        basis_tokens = sum(costs[edge] for edge in task_basis)
        full_tokens = sum(costs[edge] for edge in task_full)
        budget = (full_tokens-basis_tokens)//2
        initial = IndependentTask(task_local, task_full, task_basis)
        basis_kf = initial.kirchhoff()
        full_state = initial.clone()
        full_log = sum(full_state.add(edge) for edge in remaining)
        full_kf = full_state.kirchhoff()
        arms = {name: independent_select(initial.clone(), remaining, costs, budget, name)
                for name in ('spectral', 'cheapest', 'hash')}
        for result in arms.values():
            if result['additional_tokens'] > budget:
                raise ValueError('independent_budget_exceeded')
            result['budget_utilization'] = result['additional_tokens']/budget if budget else 1.0
            result['d_capture'] = result['logdet_gain']/full_log if full_log > 1e-10 else 1.0
            denominator = basis_kf-full_kf
            result['a_capture'] = (basis_kf-result['final_kirchhoff'])/denominator if denominator > 1e-8 else 1.0
        rows.append({'local_pairs': len(task_local), 'full_g_pairs': len(task_full),
                     'basis_g_pairs': len(task_basis), 'remaining_edges': len(remaining),
                     'basis_tokens': basis_tokens, 'full_tokens': full_tokens,
                     'additional_token_budget': budget, 'basis_kirchhoff': basis_kf,
                     'full_kirchhoff': full_kf, 'full_logdet_headroom': full_log, 'arms': arms})
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
    captures = [row['arms']['spectral']['d_capture'] for row in eligible]
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
        'spectral_median_task_d_capture_at_least_0_70': statistics.median(captures) >= 0.70,
        'fixed_counts': len(rows) == 28 and len(full) == 2745 and len(basis) == 790,
    }
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(',', ':')))
    return {'tasks': len(rows), 'eligible_cycle_tasks': len(eligible), 'full_g_pairs': len(full),
            'basis_g_pairs': len(basis), 'aggregates': aggregates,
            'spectral_not_worse_tasks': nonworse,
            'spectral_median_task_d_capture': statistics.median(captures),
            'anonymous_task_rows': rows, 'gates': gates, 'all_gates_pass': all(gates.values())}


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
    receipt_raw = checked_bytes(args.receipt, args.sha256, 1024*1024)
    metrics = reconstruct(raw)
    payload = json.loads(receipt_raw)
    if not close(payload['metrics'], metrics):
        raise ValueError('independent_mismatch')
    expected = ('G_REUSE_SPECTRAL_MIDPOINT_STRUCTURALLY_SUPPORTED' if metrics['all_gates_pass']
                else 'G_REUSE_SPECTRAL_MIDPOINT_NOT_SUPPORTED')
    if payload['status'] != expected:
        raise ValueError('status_mismatch')
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('post_hash_drift')
    return {'status': 'INDEPENDENT_G_REUSE_SPECTRAL_MIDPOINT_CLOSE',
            'receipt_sha256': args.sha256, 'metrics': metrics, 'numpy_version': np.__version__,
            'data_open_counts': dict(opened), 'selected_edge_identities_emitted': False,
            'protected_cohort_files_opened': 0, 'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
