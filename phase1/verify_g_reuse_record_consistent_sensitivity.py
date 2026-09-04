"""Independent reconstruction for record-consistent G-reuse sensitivity."""
import argparse
from collections import defaultdict
import hashlib
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
}
FIELDS = ('client', 'hardware', 'time_limit', 'execution_timeout')
CREDENTIAL = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def read_checked(path, digest, limit):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError('unsafe_input')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != digest or CREDENTIAL.search(body):
        raise ValueError('hash_or_credential_gate')
    return body


def project_pairs(body):
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


def component_count(nodes, edges):
    neighbors = {node: set() for node in nodes}
    for a, b in edges:
        neighbors[a].add(b)
        neighbors[b].add(a)
    unseen, count = set(nodes), 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            for nxt in neighbors[stack.pop()] & unseen:
                unseen.remove(nxt)
                stack.append(nxt)
    return count


def task_metrics(local, reuse, task_of):
    by_local, by_reuse = defaultdict(set), defaultdict(set)
    for edge in local:
        by_local[task_of[edge[0]]].add(edge)
    for edge in reuse:
        by_reuse[task_of[edge[0]]].add(edge)
    rows = []
    for task in sorted(by_local):
        le, re = by_local[task], by_reuse[task]
        nodes = set().union(*(set(edge) for edge in le))
        before = component_count(nodes, le)
        after = component_count(nodes, le | re)
        rows.append({'local_pairs': len(le), 'reuse_pairs': len(re), 'endpoints': len(nodes),
                     'local_components': before, 'union_components': after,
                     'rank_gain': before-after})
    rows.sort(key=lambda row: tuple(row[k] for k in ('local_pairs', 'reuse_pairs', 'endpoints',
                                                     'local_components', 'union_components', 'rank_gain')))
    gains = [row['rank_gain'] for row in rows]
    total, maximum = sum(gains), max(gains, default=0)
    return {'reuse_pairs': len(reuse), 'tasks': len(rows), 'total_rank_gain': total,
            'tasks_with_positive_rank_gain': sum(gain > 0 for gain in gains),
            'max_task_rank_gain': maximum,
            'max_task_gain_share': maximum/total if total else None,
            'anonymous_task_rows': rows}


def decide(full, filtered):
    retention = filtered['total_rank_gain']/full['total_rank_gain']
    gates = {'rank_gain_retention_at_least_0_80': retention >= 0.80,
             'at_least_20_positive_tasks': filtered['tasks_with_positive_rank_gain'] >= 20,
             'max_task_gain_share_at_most_0_20': filtered['max_task_gain_share'] <= 0.20}
    return {'full_reuse_pairs': full['reuse_pairs'], 'filtered_reuse_pairs': filtered['reuse_pairs'],
            'full_rank_gain': full['total_rank_gain'], 'filtered_rank_gain': filtered['total_rank_gain'],
            'rank_gain_retention': retention, 'tasks': filtered['tasks'],
            'tasks_with_positive_rank_gain': filtered['tasks_with_positive_rank_gain'],
            'max_task_rank_gain': filtered['max_task_rank_gain'],
            'max_task_gain_share': filtered['max_task_gain_share'], 'gates': gates,
            'all_gates_pass': all(gates.values()), 'anonymous_task_rows': filtered['anonymous_task_rows']}


def reconstruct(raw):
    local, global_all = project_pairs(raw['local']), project_pairs(raw['global'])
    grouped = json.loads(raw['cards'])
    run_of, task_of, config_of = {}, {}, {}
    for run in sorted(grouped):
        for card in grouped[run]:
            cid = card['id']
            if cid in run_of:
                raise ValueError('duplicate_card')
            run_of[cid], task_of[cid] = run, card['task']['name']
            config_of[cid] = json.dumps([card.get(k) for k in FIELDS], separators=(',', ':'), allow_nan=False)
    batch_rows = [json.loads(line) for line in raw['batches'].splitlines()]
    batches = {row['run_id']: row for row in batch_rows}
    if len(batches) != len(batch_rows) or set(batches) != set(grouped):
        raise ValueError('batch_inventory')
    local_ids = set().union(*(set(edge) for edge in local))
    local_runs = {run_of[cid] for cid in local_ids}
    local_set = set(local)
    reuse = {edge for edge in global_all if set(edge) <= local_ids and edge not in local_set
             and task_of[edge[0]] == task_of[edge[1]]
             and {run_of[cid] for cid in edge} <= local_runs}
    filtered = {edge for edge in reuse if config_of[edge[0]] == config_of[edge[1]]
                and batches[run_of[edge[0]]]['source_match_status'] == 'unique'
                and batches[run_of[edge[1]]]['source_match_status'] == 'unique'}
    if len(local) != 4689 or len(global_all) != 14206 or len(reuse) != 3058 or len(filtered) != 2745:
        raise ValueError('known_count_drift')
    return decide(task_metrics(local, reuse, task_of), task_metrics(local, filtered, task_of))


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
        if path in allowed:
            opened[str(path)] += 1
        elif path.suffix.lower() not in ('.py', '.pyc'):
            raise PermissionError('unlisted_data')
    sys.addaudithook(guard)
    raw = {name: read_checked(path, digest, 650*1024**2)
           for name, (path, digest) in FILES.items()}
    receipt_raw = read_checked(args.receipt, args.sha256, 256*1024)
    if json.loads(raw['manifest']).get('run_batch_manifest.jsonl') != FILES['batches'][1]:
        raise ValueError('manifest_binding')
    metrics = reconstruct(raw)
    payload = json.loads(receipt_raw)
    if payload['metrics'] != metrics:
        raise ValueError('independent_mismatch')
    expected = ('RECORD_CONSISTENT_G_REUSE_SENSITIVITY_SUPPORTED' if metrics['all_gates_pass']
                else 'RECORD_CONSISTENT_G_REUSE_SENSITIVITY_NOT_SUPPORTED')
    if payload['status'] != expected:
        raise ValueError('status_mismatch')
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('post_hash_drift')
    return {'status': 'INDEPENDENT_RECORD_CONSISTENT_SENSITIVITY_EXACT',
            'receipt_sha256': args.sha256, 'metrics': metrics, 'data_open_counts': dict(opened),
            'protected_cohort_files_opened': 0, 'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
