"""Independent set/BFS/Kruskal reconstruction for the minimum-token G-reuse basis."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path('/research/d7/spc/yzyang4')
FILES = {
    'local': (ROOT/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl',
              '0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e'),
    'global': (Path('/tmp/global-hash-hardened-20260823.9ntGvq/global_train.jsonl'),
               'd9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010'),
    'cards': (ROOT/'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json',
              '5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb'),
    'batches': (ROOT/'senior-true-batch-identity-support/a466888-v3/producer_1/run_batch_manifest.jsonl',
                '60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'),
    'manifest': (ROOT/'senior-true-batch-identity-support/a466888-v3/producer_1/sha256_manifest.json',
                 'e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92'),
    'lengths': (Path('/tmp/historical-input-20260904-12Eo0Z8F/run-r2/endpoint_lengths.csv'),
                '789e87a9d6e6f44a1a526a0bb18330c425216a36f4f75341abf570dd9f11681a'),
}
FIELDS = ('client', 'hardware', 'time_limit', 'execution_timeout')
CREDENTIAL = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def checked_bytes(path, digest, limit=650*1024**2):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('unsafe_input')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != digest or CREDENTIAL.search(body):
        raise ValueError('hash_or_credential_gate')
    return body


def parse_pairs(body):
    edges = []
    for line in body.splitlines():
        row = json.loads(line)
        if row.get('intask_split') != 'train':
            raise ValueError('nontrain')
        edge = tuple(sorted((row['better'], row['worse'])))
        if edge[0] == edge[1]:
            raise ValueError('self_pair')
        edges.append(edge)
    if len(edges) != len(set(edges)):
        raise ValueError('duplicate_pair')
    return edges


class Disjoint:
    def __init__(self, nodes):
        self.parent = {node: node for node in nodes}

    def root(self, node):
        trail = []
        while self.parent[node] != node:
            trail.append(node)
            node = self.parent[node]
        for prior in trail:
            self.parent[prior] = node
        return node

    def merge(self, left, right):
        left, right = self.root(left), self.root(right)
        if left == right:
            return False
        self.parent[max(left, right)] = min(left, right)
        return True


def count_components(nodes, edges):
    graph = {node: set() for node in nodes}
    for left, right in edges:
        graph[left].add(right); graph[right].add(left)
    unseen, count = set(nodes), 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            neighbors = graph[stack.pop()] & unseen
            unseen.difference_update(neighbors)
            stack.extend(neighbors)
    return count


def exposure(edges):
    degree = Counter(node for edge in edges for node in edge)
    values = sorted(degree.values(), reverse=True)
    total = sum(values)
    return {'unique_endpoints': len(values), 'endpoint_visits': total,
            'max_endpoint_degree': values[0] if values else 0,
            'top_decile_visit_share': sum(values[:(len(values)+9)//10])/total if total else None}


def reconstruct(raw):
    local, global_all = parse_pairs(raw['local']), parse_pairs(raw['global'])
    grouped = json.loads(raw['cards'])
    run_of, task_of, config_of = {}, {}, {}
    for run in sorted(grouped):
        for card in grouped[run]:
            cid = card['id']
            if cid in run_of:
                raise ValueError('duplicate_card')
            run_of[cid], task_of[cid] = run, card['task']['name']
            config_of[cid] = json.dumps([card.get(field) for field in FIELDS], separators=(',', ':'), allow_nan=False)
    batch_rows = [json.loads(line) for line in raw['batches'].splitlines()]
    batches = {row['run_id']: row for row in batch_rows}
    if len(batches) != len(batch_rows) or set(batches) != set(grouped):
        raise ValueError('batch_inventory')
    if json.loads(raw['manifest']).get('run_batch_manifest.jsonl') != FILES['batches'][1]:
        raise ValueError('manifest_binding')
    local_ids = set().union(*(set(edge) for edge in local))
    local_runs = {run_of[node] for node in local_ids}
    local_set = set(local)
    reuse = {edge for edge in global_all if set(edge) <= local_ids and edge not in local_set
             and task_of[edge[0]] == task_of[edge[1]] and {run_of[node] for node in edge} <= local_runs}
    full = {edge for edge in reuse if config_of[edge[0]] == config_of[edge[1]]
            and batches[run_of[edge[0]]]['source_match_status'] == 'unique'
            and batches[run_of[edge[1]]]['source_match_status'] == 'unique'}
    rows = list(csv.DictReader(io.StringIO(raw['lengths'].decode())))
    ordered = sorted(local_ids)
    if len(rows) != len(ordered):
        raise ValueError('length_coverage')
    lengths = {}
    for index, (node, row) in enumerate(zip(ordered, rows)):
        raw_tokens, valid = int(row['raw_tokens']), int(row['valid_tokens'])
        if set(row) != {'ordinal', 'raw_tokens', 'valid_tokens', 'encoding_sha256'} or int(row['ordinal']) != index:
            raise ValueError('length_schema')
        if valid != min(raw_tokens, 16384) or raw_tokens <= 0:
            raise ValueError('length_value')
        if len(row['encoding_sha256']) != 64 or any(char not in '0123456789abcdef' for char in row['encoding_sha256']):
            raise ValueError('encoding_hash_shape')
        lengths[node] = valid
    uf = Disjoint(local_ids)
    for edge in local:
        uf.merge(*edge)
    basis = []
    for edge in sorted(full, key=lambda pair: (lengths[pair[0]]+lengths[pair[1]], pair)):
        if uf.merge(*edge):
            basis.append(edge)
    by_local, by_full, by_basis = defaultdict(set), defaultdict(set), defaultdict(set)
    for edge in local: by_local[task_of[edge[0]]].add(edge)
    for edge in full: by_full[task_of[edge[0]]].add(edge)
    for edge in basis: by_basis[task_of[edge[0]]].add(edge)
    task_rows = []
    for task in sorted(by_local):
        nodes = set().union(*(set(edge) for edge in by_local[task]))
        before = count_components(nodes, by_local[task])
        full_gain = before-count_components(nodes, by_local[task] | by_full[task])
        basis_gain = before-count_components(nodes, by_local[task] | by_basis[task])
        task_rows.append({'local_pairs': len(by_local[task]), 'full_pairs': len(by_full[task]),
                          'basis_pairs': len(by_basis[task]), 'full_gain': full_gain,
                          'basis_gain': basis_gain})
    task_rows.sort(key=lambda row: tuple(row[key] for key in
                   ('local_pairs', 'full_pairs', 'basis_pairs', 'full_gain', 'basis_gain')))
    full_gain, basis_gain = sum(row['full_gain'] for row in task_rows), sum(row['basis_gain'] for row in task_rows)
    full_tokens = sum(lengths[a]+lengths[b] for a, b in full)
    basis_tokens = sum(lengths[a]+lengths[b] for a, b in basis)
    local_tokens = sum(lengths[a]+lengths[b] for a, b in local)
    reduction = 1-basis_tokens/full_tokens
    gates = {'per_task_rank_gain_exact': all(row['full_gain'] == row['basis_gain'] for row in task_rows),
             'total_rank_gain_exact_790': full_gain == basis_gain == 790,
             'g_stage_token_reduction_at_least_0_60': reduction >= 0.60}
    if len(local) != 4689 or len(global_all) != 14206 or len(reuse) != 3058 or len(full) != 2745:
        raise ValueError('known_count_drift')
    return {'filtered_reuse_pairs': len(full), 'basis_pairs': len(basis),
            'pair_reduction_fraction': 1-len(basis)/len(full),
            'full_rank_gain': full_gain, 'basis_rank_gain': basis_gain,
            'tasks': len(task_rows), 'tasks_exact': sum(row['full_gain'] == row['basis_gain'] for row in task_rows),
            'full_g_valid_tokens': full_tokens, 'basis_g_valid_tokens': basis_tokens,
            'g_token_reduction_fraction': reduction, 'local_once_valid_tokens': local_tokens,
            'full_then_local_valid_tokens': full_tokens+local_tokens,
            'basis_then_local_valid_tokens': basis_tokens+local_tokens,
            'full_exposure': exposure(full), 'basis_exposure': exposure(basis),
            'gates': gates, 'all_gates_pass': all(gates.values()), 'anonymous_task_rows': task_rows}


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
                (isinstance(flags, int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))):
            raise PermissionError('read_only')
        if path in allowed: opened[str(path)] += 1
        elif path.suffix.lower() not in ('.py', '.pyc'): raise PermissionError('unlisted_data')
    sys.addaudithook(guard)
    raw = {name: checked_bytes(path, digest) for name, (path, digest) in FILES.items()}
    receipt_raw = checked_bytes(args.receipt, args.sha256, 256*1024)
    metrics = reconstruct(raw)
    payload = json.loads(receipt_raw)
    if payload['metrics'] != metrics:
        raise ValueError('independent_mismatch')
    expected = ('G_REUSE_MIN_TOKEN_BASIS_STRUCTURAL_COST_SUPPORTED' if metrics['all_gates_pass']
                else 'G_REUSE_MIN_TOKEN_BASIS_NOT_SUPPORTED')
    if payload['status'] != expected:
        raise ValueError('status_mismatch')
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('post_hash_drift')
    return {'status': 'INDEPENDENT_G_REUSE_MIN_TOKEN_BASIS_EXACT',
            'receipt_sha256': args.sha256, 'metrics': metrics, 'data_open_counts': dict(opened),
            'selected_edge_identities_emitted': False, 'protected_cohort_files_opened': 0,
            'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
