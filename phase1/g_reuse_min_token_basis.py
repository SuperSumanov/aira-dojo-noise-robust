"""Minimum-token G-reuse comparison basis; historical structural/cost diagnostic only."""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_task_breadth import derive_reuse, summarize
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project

LENGTHS = (Path('/tmp/historical-input-20260904-12Eo0Z8F/run-r2/endpoint_lengths.csv'),
           '789e87a9d6e6f44a1a526a0bb18330c425216a36f4f75341abf570dd9f11681a')


def read_lengths(local_ids, rows):
    ordered = sorted(local_ids)
    check(len(rows) == len(ordered), 'length_coverage')
    result = {}
    for index, (cid, row) in enumerate(zip(ordered, rows)):
        check(set(row) == {'ordinal', 'raw_tokens', 'valid_tokens', 'encoding_sha256'}, 'length_schema')
        raw, valid = int(row['raw_tokens']), int(row['valid_tokens'])
        check(int(row['ordinal']) == index and raw > 0 and valid == min(raw, 16384), 'length_value')
        check(len(row['encoding_sha256']) == 64 and
              all(char in '0123456789abcdef' for char in row['encoding_sha256']), 'encoding_hash_shape')
        result[cid] = valid
    return result


class UnionFind:
    def __init__(self, nodes):
        self.parent = {node: node for node in nodes}

    def find(self, node):
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, left, right):
        left, right = self.find(left), self.find(right)
        if left == right:
            return False
        if left > right:
            left, right = right, left
        self.parent[right] = left
        return True


def choose_basis(local, reuse, lengths):
    nodes = set(lengths)
    uf = UnionFind(nodes)
    for left, right in local:
        check(uf.union(left, right) or uf.find(left) == uf.find(right), 'local_union')
    selected = []
    for edge in sorted(reuse, key=lambda pair: (lengths[pair[0]]+lengths[pair[1]], pair)):
        if uf.union(*edge):
            selected.append(edge)
    return selected


def task_gain_rows(local, full, basis, task_of):
    full_metrics = summarize(local, full, task_of)
    basis_metrics = summarize(local, basis, task_of)
    def keyed(edges):
        by_task = defaultdict(list)
        for edge in edges:
            by_task[task_of[edge[0]]].append(edge)
        return by_task
    by_local, by_full, by_basis = keyed(local), keyed(full), keyed(basis)
    rows = []
    for task in sorted(by_local):
        fm = summarize(by_local[task], by_full[task], task_of)
        bm = summarize(by_local[task], by_basis[task], task_of)
        rows.append({'local_pairs': len(by_local[task]), 'full_pairs': len(by_full[task]),
                     'basis_pairs': len(by_basis[task]), 'full_gain': fm['total_rank_gain'],
                     'basis_gain': bm['total_rank_gain']})
    rows.sort(key=lambda row: tuple(row.values()))
    return full_metrics, basis_metrics, rows


def exposure(edges):
    degree = Counter(node for edge in edges for node in edge)
    values = sorted(degree.values(), reverse=True)
    total = sum(values)
    return {'unique_endpoints': len(values), 'endpoint_visits': total,
            'max_endpoint_degree': values[0] if values else 0,
            'top_decile_visit_share': sum(values[:(len(values)+9)//10])/total if total else None}


def metrics(local, full, basis, task_of, lengths):
    full_graph, basis_graph, task_rows = task_gain_rows(local, full, basis, task_of)
    full_tokens = sum(lengths[a]+lengths[b] for a, b in full)
    basis_tokens = sum(lengths[a]+lengths[b] for a, b in basis)
    reduction = 1-basis_tokens/full_tokens
    task_exact = all(row['full_gain'] == row['basis_gain'] for row in task_rows)
    gates = {'per_task_rank_gain_exact': task_exact,
             'total_rank_gain_exact_790': basis_graph['total_rank_gain'] == full_graph['total_rank_gain'] == 790,
             'g_stage_token_reduction_at_least_0_60': reduction >= 0.60}
    local_tokens = sum(lengths[a]+lengths[b] for a, b in local)
    return {'filtered_reuse_pairs': len(full), 'basis_pairs': len(basis),
            'pair_reduction_fraction': 1-len(basis)/len(full),
            'full_rank_gain': full_graph['total_rank_gain'], 'basis_rank_gain': basis_graph['total_rank_gain'],
            'tasks': len(task_rows), 'tasks_exact': sum(row['full_gain'] == row['basis_gain'] for row in task_rows),
            'full_g_valid_tokens': full_tokens, 'basis_g_valid_tokens': basis_tokens,
            'g_token_reduction_fraction': reduction, 'local_once_valid_tokens': local_tokens,
            'full_then_local_valid_tokens': full_tokens+local_tokens,
            'basis_then_local_valid_tokens': basis_tokens+local_tokens,
            'full_exposure': exposure(full), 'basis_exposure': exposure(basis),
            'gates': gates, 'all_gates_pass': all(gates.values()), 'anonymous_task_rows': task_rows}


def main():
    extras = [p for p, _ in EXTRA.values()] + [LENGTHS[0]]
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
    reuse = derive_reuse(local, global_all, run_of, task_of)
    filtered = record_consistent(reuse, cards, batches)
    local_ids = {node for edge in local for node in edge}
    with LENGTHS[0].open(newline='') as handle:
        lengths = read_lengths(local_ids, list(csv.DictReader(handle)))
    basis = choose_basis(local, filtered, lengths)
    check(len(filtered) == 2745, 'filtered_count_drift')
    result = metrics(local, filtered, basis, task_of, lengths)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = ('G_REUSE_MIN_TOKEN_BASIS_STRUCTURAL_COST_SUPPORTED' if result['all_gates_pass']
              else 'G_REUSE_MIN_TOKEN_BASIS_NOT_SUPPORTED')
    return {'status': status, 'metrics': result,
            'input_sha256': {**{key: value for key, (_, value) in INPUTS.items()},
                             **{key: value for key, (_, value) in EXTRA.items()}, 'lengths': LENGTHS[1]},
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'selected_edge_identities_emitted': False, 'pool_written': False,
            'source_config_experiment_gates_remain': True, 'protected_cohort_files_opened': 0,
            'data_open_counts': dict(opened), 'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
