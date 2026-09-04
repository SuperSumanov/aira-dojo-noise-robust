"""Independent BFS/set verifier for the G-reuse task-breadth receipt."""
import argparse
from collections import defaultdict, deque
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
}
CREDENTIAL = re.compile(rb'(?i)(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def read_checked(path, digest, cap):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > cap:
        raise ValueError('unsafe_input')
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != digest or CREDENTIAL.search(body):
        raise ValueError('hash_or_credential_gate')
    return body


def parse_edges(body):
    result = set()
    for raw in body.splitlines():
        row = json.loads(raw)
        if row.get('intask_split') != 'train' or row['better'] == row['worse']:
            raise ValueError('invalid_pair')
        result.add(tuple(sorted((row['better'], row['worse']))))
    if len(result) != len(body.splitlines()) or not result:
        raise ValueError('duplicate_or_empty_pairs')
    return result


def count_components(nodes, edges):
    adjacency = {node: set() for node in nodes}
    for a, b in edges:
        adjacency[a].add(b)
        adjacency[b].add(a)
    seen, count = set(), 0
    for start in sorted(nodes):
        if start in seen:
            continue
        count += 1
        seen.add(start)
        queue = deque([start])
        while queue:
            for neighbor in adjacency[queue.popleft()]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
    return count


def recompute(local, global_all, grouped):
    run_of, task_of = {}, {}
    for run, cards in grouped.items():
        for card in cards:
            cid = card['id']
            if cid in run_of:
                raise ValueError('duplicate_card')
            run_of[cid], task_of[cid] = run, card['task']['name']
    local_ids = set().union(*(set(edge) for edge in local))
    local_runs = {run_of[v] for v in local_ids}
    reuse = {edge for edge in global_all
             if set(edge) <= set(run_of)
             and task_of[edge[0]] == task_of[edge[1]]
             and {run_of[v] for v in edge} <= local_runs
             and edge not in local
             and set(edge) <= local_ids}
    by_l, by_r = defaultdict(set), defaultdict(set)
    for edge in local:
        by_l[task_of[edge[0]]].add(edge)
    for edge in reuse:
        by_r[task_of[edge[0]]].add(edge)
    rows = []
    for task in by_l:
        l_edges, r_edges = by_l[task], by_r[task]
        nodes = set().union(*(set(edge) for edge in l_edges))
        before = count_components(nodes, l_edges)
        after = count_components(nodes, l_edges | r_edges)
        rows.append(dict(local_pairs=len(l_edges), reuse_pairs=len(r_edges), endpoints=len(nodes),
                         local_components=before, union_components=after, rank_gain=before-after))
    anonymous = sorted(rows, key=lambda row: tuple(row[k] for k in
        ('local_pairs', 'reuse_pairs', 'endpoints', 'local_components', 'union_components', 'rank_gain')))
    total = sum(row['rank_gain'] for row in rows)
    positive = sum(row['rank_gain'] > 0 for row in rows)
    maximum = max(row['rank_gain'] for row in rows)
    max_share = maximum / total
    leave = (total - maximum) / total
    gates = {'at_least_20_positive_tasks': positive >= 20,
             'max_task_gain_share_at_most_0_20': max_share <= 0.20,
             'leave_any_task_retains_at_least_0_80': leave >= 0.80}
    return len(reuse), dict(tasks=len(rows), tasks_with_positive_rank_gain=positive,
        total_rank_gain=total, max_task_rank_gain=maximum, max_task_gain_share=max_share,
        min_leave_one_task_gain_fraction=leave, gates=gates,
        all_gates_pass=all(gates.values()), anonymous_task_rows=anonymous)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    receipt = Path(args.receipt).absolute()
    allowed = {p.absolute() for p, _ in FILES.values()} | {receipt}

    def hook(event, params):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise PermissionError('offline')
        if event != 'open' or not isinstance(params[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(params[0])).absolute()
        mode, flags = params[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if write:
            raise PermissionError('no_writes')
        if path in allowed:
            if path.resolve() != path:
                raise PermissionError('linked_input')
        elif path.suffix not in ('.py', '.pyc'):
            raise PermissionError('unlisted_file')

    sys.addaudithook(hook)
    payload = json.loads(read_checked(receipt, args.sha256, 256*1024))
    raw = {key: read_checked(path, digest, 650*1024**2) for key, (path, digest) in FILES.items()}
    local, global_all = parse_edges(raw['local']), parse_edges(raw['global'])
    reuse_count, metrics = recompute(local, global_all, json.loads(raw['cards']))
    if len(local) != 4689 or len(global_all) != 14206 or reuse_count != 3058:
        raise ValueError('known_input_drift')
    if metrics['tasks'] != 28 or metrics['total_rank_gain'] != 924:
        raise ValueError('known_aggregate_drift')
    expected_status = ('HISTORICAL_G_REUSE_TASK_BREADTH_STRUCTURALLY_SUPPORTED'
                       if metrics['all_gates_pass'] else 'HISTORICAL_G_REUSE_TASK_BREADTH_NOT_SUPPORTED')
    if payload['status'] != expected_status or payload['metrics'] != metrics:
        raise ValueError('independent_mismatch')
    if payload['input_sha256'] != {k: h for k, (_, h) in FILES.items()}:
        raise ValueError('binding_mismatch')
    for key in ('protected_cohort_files_opened', 'gpu_jobs', 'api_calls', 'model_fits', 'training_pools_written'):
        if payload[key] != 0:
            raise ValueError('scope_mismatch')
    for path, digest in [*FILES.values(), (receipt, args.sha256)]:
        with path.open('rb') as handle:
            observed = hashlib.file_digest(handle, 'sha256').hexdigest()
        if observed != digest:
            raise ValueError('post_hash_drift')
    return dict(status='INDEPENDENT_G_REUSE_TASK_BREADTH_EXACT', receipt_sha256=args.sha256,
                metrics=metrics, gpu_jobs=0, api_calls=0, model_fits=0)


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
