"""Independent reconstruction of cap/task robustness for the G-reuse basis."""
import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys

from phase1.verify_g_reuse_min_token_basis import (
    FILES, Disjoint, checked_bytes, count_components, parse_pairs,
)

CAPS = (4096, 8192, 16384, None)
FIELDS = ('client', 'hardware', 'time_limit', 'execution_timeout')


def independent_reconstruct(raw):
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
    local_runs, local_set = {run_of[node] for node in local_ids}, set(local)
    reuse = {edge for edge in global_all if set(edge) <= local_ids and edge not in local_set
             and task_of[edge[0]] == task_of[edge[1]]
             and {run_of[node] for node in edge} <= local_runs}
    full = {edge for edge in reuse if config_of[edge[0]] == config_of[edge[1]]
            and batches[run_of[edge[0]]]['source_match_status'] == 'unique'
            and batches[run_of[edge[1]]]['source_match_status'] == 'unique'}
    length_rows = list(csv.DictReader(io.StringIO(raw['lengths'].decode())))
    ordered = sorted(local_ids)
    if len(length_rows) != len(ordered):
        raise ValueError('length_coverage')
    raw_lengths = {}
    for index, (node, row) in enumerate(zip(ordered, length_rows)):
        raw_tokens, valid = int(row['raw_tokens']), int(row['valid_tokens'])
        if set(row) != {'ordinal', 'raw_tokens', 'valid_tokens', 'encoding_sha256'}:
            raise ValueError('length_schema')
        if int(row['ordinal']) != index or raw_tokens <= 0 or valid != min(raw_tokens, 16384):
            raise ValueError('length_value')
        if len(row['encoding_sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['encoding_sha256']):
            raise ValueError('encoding_hash_shape')
        raw_lengths[node] = raw_tokens
    if (len(local), len(global_all), len(reuse), len(full)) != (4689, 14206, 3058, 2745):
        raise ValueError('known_count_drift')

    local_by_task, full_by_task = defaultdict(set), defaultdict(set)
    for edge in local:
        local_by_task[task_of[edge[0]]].add(edge)
    for edge in full:
        full_by_task[task_of[edge[0]]].add(edge)
    scenarios, common_qualifying = {}, None
    for cap in CAPS:
        label = 'raw' if cap is None else str(cap)
        lengths = {node: raw_value if cap is None else min(raw_value, cap)
                   for node, raw_value in raw_lengths.items()}
        forest = Disjoint(local_ids)
        for edge in local:
            forest.merge(*edge)
        basis = []
        for edge in sorted(full, key=lambda item: (lengths[item[0]] + lengths[item[1]], item)):
            if forest.merge(*edge):
                basis.append(edge)
        basis_by_task = defaultdict(set)
        for edge in basis:
            basis_by_task[task_of[edge[0]]].add(edge)
        identified_rows, full_gain, basis_gain, exact = {}, 0, 0, 0
        for task in sorted(local_by_task):
            nodes = set().union(*(set(edge) for edge in local_by_task[task]))
            before = count_components(nodes, local_by_task[task])
            fg = before - count_components(nodes, local_by_task[task] | full_by_task[task])
            bg = before - count_components(nodes, local_by_task[task] | basis_by_task[task])
            full_gain, basis_gain = full_gain + fg, basis_gain + bg
            exact += fg == bg
            full_tokens = sum(lengths[a] + lengths[b] for a, b in full_by_task[task])
            basis_tokens = sum(lengths[a] + lengths[b] for a, b in basis_by_task[task])
            saved = full_tokens - basis_tokens
            identified_rows[task] = {'full_pairs': len(full_by_task[task]),
                                     'basis_pairs': len(basis_by_task[task]),
                                     'full_tokens': full_tokens, 'basis_tokens': basis_tokens,
                                     'saved_tokens': saved, 'reduction_fraction': saved/full_tokens}
        qualifying = {task for task, row in identified_rows.items() if row['reduction_fraction'] >= 0.50}
        common_qualifying = qualifying if common_qualifying is None else common_qualifying & qualifying
        rows = list(identified_rows.values())
        rows.sort(key=lambda row: tuple(row[key] for key in
                  ('full_pairs', 'basis_pairs', 'full_tokens', 'basis_tokens',
                   'saved_tokens', 'reduction_fraction')))
        total_full = sum(row['full_tokens'] for row in rows)
        total_basis = sum(row['basis_tokens'] for row in rows)
        total_saved = total_full - total_basis
        leave_one = [1 - (total_basis-row['basis_tokens'])/(total_full-row['full_tokens']) for row in rows]
        scenarios[label] = {'basis_pairs': len(basis), 'full_rank_gain': full_gain,
                            'basis_rank_gain': basis_gain, 'tasks_exact': exact,
                            'per_task_rank_gain_exact': exact == len(rows),
                            'full_tokens': total_full, 'basis_tokens': total_basis,
                            'reduction_fraction': total_saved/total_full,
                            'leave_one_task_min_reduction': min(leave_one),
                            'max_task_saved_share': max(row['saved_tokens'] for row in rows)/total_saved,
                            'tasks_reduction_at_least_0_50': len(qualifying),
                            'anonymous_task_rows': rows}
    gates = {
        'all_caps_per_task_and_total_rank_exact':
            all(row['per_task_rank_gain_exact'] and row['full_rank_gain'] == row['basis_rank_gain'] == 790
                for row in scenarios.values()),
        'all_caps_token_reduction_at_least_0_60':
            all(row['reduction_fraction'] >= 0.60 for row in scenarios.values()),
        'all_caps_leave_one_task_reduction_at_least_0_60':
            all(row['leave_one_task_min_reduction'] >= 0.60 for row in scenarios.values()),
        'all_caps_max_task_saved_share_at_most_0_20':
            all(row['max_task_saved_share'] <= 0.20 for row in scenarios.values()),
        'tasks_ge_0_50_in_every_cap_at_least_20_of_28': len(common_qualifying) >= 20,
    }
    return {'filtered_reuse_pairs': len(full), 'tasks': len(next(iter(scenarios.values()))['anonymous_task_rows']),
            'tasks_reduction_at_least_0_50_in_every_cap': len(common_qualifying),
            'scenarios': scenarios, 'gates': gates, 'all_gates_pass': all(gates.values())}


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
    metrics = independent_reconstruct(raw)
    payload = json.loads(receipt_raw)
    if payload['metrics'] != metrics:
        raise ValueError('independent_mismatch')
    expected = ('G_REUSE_MIN_TOKEN_BASIS_COST_ROBUST_ACROSS_CAPS_AND_TASKS'
                if metrics['all_gates_pass'] else 'G_REUSE_MIN_TOKEN_BASIS_COST_NOT_ROBUST')
    if payload['status'] != expected:
        raise ValueError('status_mismatch')
    for path, digest in [*FILES.values(), (args.receipt, args.sha256)]:
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('post_hash_drift')
    return {'status': 'INDEPENDENT_G_REUSE_MIN_TOKEN_ROBUSTNESS_EXACT',
            'receipt_sha256': args.sha256, 'metrics': metrics,
            'data_open_counts': dict(opened), 'selected_edge_identities_emitted': False,
            'protected_cohort_files_opened': 0, 'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
