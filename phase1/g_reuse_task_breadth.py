"""Anonymous per-task breadth of historical G-reuse graph-rank gain.

This is a label-blind structural diagnostic, not a fit or an effect result.
"""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys

BASE = Path('/research/d7/spc/yzyang4')
INPUTS = {
    'local': (BASE/'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl',
              '0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e'),
    'global': (Path('/tmp/global-hash-hardened-20260823.9ntGvq/global_train.jsonl'),
               'd9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010'),
    'cards': (BASE/'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json',
              '5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb'),
}
CREDENTIAL = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def require(ok, code):
    if not ok:
        raise ValueError(code)


def install_guard():
    allowed = {p.absolute() for p, _ in INPUTS.values()}
    opened = Counter()

    def hook(event, args):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise PermissionError('network_or_process_forbidden')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).absolute()
        mode, flags = args[1:3]
        write = isinstance(mode, str) and any(c in mode for c in 'wax+')
        write |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if write:
            raise PermissionError('read_only')
        if path in allowed:
            require(path.resolve() == path, 'linked_input')
            opened[str(path)] += 1
        elif path.suffix not in ('.py', '.pyc'):
            raise PermissionError('unlisted_data')

    sys.addaudithook(hook)
    return opened


def checked_bytes(path, digest, cap=650*1024**2, scan=True):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= cap, 'unsafe_input')
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == digest, 'input_hash_drift')
    if scan:
        require(CREDENTIAL.search(body) is None, 'credential_shape')
    return body


def read_pairs(body):
    edges = []
    for raw in body.splitlines():
        row = json.loads(raw)
        require(row.get('intask_split') == 'train', 'non_train_row')
        a, b = row['better'], row['worse']
        require(isinstance(a, str) and isinstance(b, str) and a and b and a != b, 'invalid_pair')
        edges.append(tuple(sorted((a, b))))
    require(edges and len(edges) == len(set(edges)), 'empty_or_duplicate_pairs')
    return edges


def identity_map(body):
    run_of, task_of = {}, {}
    grouped = json.loads(body)
    for run, cards in grouped.items():
        require(isinstance(run, str) and run, 'invalid_run')
        for card in cards:
            cid, task = card['id'], card['task']['name']
            require(isinstance(cid, str) and cid and cid not in run_of, 'duplicate_card')
            require(isinstance(task, str) and task, 'invalid_task')
            run_of[cid], task_of[cid] = run, task
    return run_of, task_of


def component_count(nodes, edges):
    parent = {node: node for node in nodes}

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    return len({find(node) for node in nodes})


def derive_reuse(local, global_all, run_of, task_of):
    local_set = set(local)
    local_ids = {v for edge in local for v in edge}
    require(local_ids <= run_of.keys(), 'local_identity_missing')
    require(all(task_of[a] == task_of[b] for a, b in local), 'local_cross_task')
    local_runs = {run_of[v] for v in local_ids}
    reuse = []
    for a, b in global_all:
        if a not in run_of or b not in run_of:
            continue
        if task_of[a] != task_of[b]:
            continue
        if run_of[a] not in local_runs or run_of[b] not in local_runs:
            continue
        if (a, b) in local_set:
            continue
        if a in local_ids and b in local_ids:
            reuse.append((a, b))
    require(len(reuse) == len(set(reuse)), 'duplicate_reuse')
    return reuse


def summarize(local, reuse, task_of):
    by_task_local, by_task_reuse = defaultdict(list), defaultdict(list)
    for edge in local:
        by_task_local[task_of[edge[0]]].append(edge)
    for edge in reuse:
        by_task_reuse[task_of[edge[0]]].append(edge)
    rows = []
    for task in sorted(by_task_local):
        l_edges = by_task_local[task]
        r_edges = by_task_reuse[task]
        nodes = {v for edge in l_edges for v in edge}
        before = component_count(nodes, l_edges)
        after = component_count(nodes, l_edges + r_edges)
        gain = before - after
        require(gain >= 0, 'negative_rank_gain')
        rows.append(dict(local_pairs=len(l_edges), reuse_pairs=len(r_edges), endpoints=len(nodes),
                         local_components=before, union_components=after, rank_gain=gain))
    anonymous = sorted(rows, key=lambda row: tuple(row[k] for k in
        ('local_pairs', 'reuse_pairs', 'endpoints', 'local_components', 'union_components', 'rank_gain')))
    total_gain = sum(row['rank_gain'] for row in rows)
    require(total_gain > 0, 'zero_total_gain')
    positive = sum(row['rank_gain'] > 0 for row in rows)
    maximum = max(row['rank_gain'] for row in rows)
    maximum_share = maximum / total_gain
    min_leave_one_fraction = (total_gain - maximum) / total_gain
    gates = {
        'at_least_20_positive_tasks': positive >= 20,
        'max_task_gain_share_at_most_0_20': maximum_share <= 0.20,
        'leave_any_task_retains_at_least_0_80': min_leave_one_fraction >= 0.80,
    }
    return dict(tasks=len(rows), tasks_with_positive_rank_gain=positive,
                total_rank_gain=total_gain, max_task_rank_gain=maximum,
                max_task_gain_share=maximum_share,
                min_leave_one_task_gain_fraction=min_leave_one_fraction,
                gates=gates, all_gates_pass=all(gates.values()), anonymous_task_rows=anonymous)


def main():
    opened = install_guard()
    raw = {key: checked_bytes(path, digest) for key, (path, digest) in INPUTS.items()}
    local, global_all = read_pairs(raw['local']), read_pairs(raw['global'])
    run_of, task_of = identity_map(raw['cards'])
    require(len(local) == 4689 and len(global_all) == 14206, 'input_size_drift')
    reuse = derive_reuse(local, global_all, run_of, task_of)
    require(len(reuse) == 3058, 'reuse_count_drift')
    metrics = summarize(local, reuse, task_of)
    require(metrics['tasks'] == 28 and metrics['total_rank_gain'] == 924, 'known_aggregate_drift')
    require(metrics == summarize(list(reversed(local)), list(reversed(reuse)), task_of), 'order_drift')
    for path, digest in INPUTS.values():
        checked_bytes(path, digest, scan=False)
    status = ('HISTORICAL_G_REUSE_TASK_BREADTH_STRUCTURALLY_SUPPORTED'
              if metrics['all_gates_pass'] else 'HISTORICAL_G_REUSE_TASK_BREADTH_NOT_SUPPORTED')
    return dict(status=status, metrics=metrics, input_sha256={k: h for k, (_, h) in INPUTS.items()},
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                data_open_counts=dict(opened), protected_cohort_files_opened=0,
                gpu_jobs=0, api_calls=0, model_fits=0, training_pools_written=0,
                limitations=['Adding edges cannot reduce incidence rank; only breadth/concentration is tested.',
                             'Derived pairs are correlated constraints, not independent execution labels.',
                             'Source/config/experiment-closure and model-effect gates remain unresolved.'])


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
