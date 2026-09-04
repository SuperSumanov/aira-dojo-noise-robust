"""Frozen cap/task robustness for the minimum-token G-reuse basis."""
from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path

from phase1.g_reuse_min_token_basis import LENGTHS, choose_basis, task_gain_rows
from phase1.g_reuse_record_consistent_sensitivity import EXTRA, record_consistent
from phase1.g_reuse_task_breadth import derive_reuse
from phase1.historical_global_local_source_gate import project_batches, project_cards
from phase1.historical_label_reuse_support import INPUTS, check, checked, install_guard, pairs, project

CAPS = (4096, 8192, 16384, None)


def read_raw_lengths(local_ids, rows):
    ordered = sorted(local_ids)
    check(len(rows) == len(ordered), 'length_coverage')
    result = {}
    for index, (cid, row) in enumerate(zip(ordered, rows)):
        check(set(row) == {'ordinal', 'raw_tokens', 'valid_tokens', 'encoding_sha256'}, 'length_schema')
        raw, valid = int(row['raw_tokens']), int(row['valid_tokens'])
        check(int(row['ordinal']) == index and raw > 0 and valid == min(raw, 16384), 'length_value')
        check(len(row['encoding_sha256']) == 64 and
              all(char in '0123456789abcdef' for char in row['encoding_sha256']), 'encoding_hash_shape')
        result[cid] = raw
    return result


def cost_stats(full, basis, task_of, lengths):
    by_full, by_basis = defaultdict(list), defaultdict(list)
    for edge in full:
        by_full[task_of[edge[0]]].append(edge)
    for edge in basis:
        by_basis[task_of[edge[0]]].append(edge)
    identified_rows = {}
    for task in sorted(by_full):
        full_tokens = sum(lengths[a] + lengths[b] for a, b in by_full[task])
        basis_tokens = sum(lengths[a] + lengths[b] for a, b in by_basis[task])
        saved = full_tokens - basis_tokens
        identified_rows[task] = {'full_pairs': len(by_full[task]), 'basis_pairs': len(by_basis[task]),
                                 'full_tokens': full_tokens, 'basis_tokens': basis_tokens,
                                 'saved_tokens': saved, 'reduction_fraction': saved / full_tokens}
    qualifying = {task for task, row in identified_rows.items() if row['reduction_fraction'] >= 0.50}
    rows = list(identified_rows.values())
    rows.sort(key=lambda row: tuple(row.values()))
    total_full = sum(row['full_tokens'] for row in rows)
    total_basis = sum(row['basis_tokens'] for row in rows)
    total_saved = total_full - total_basis
    leave_one = [1 - (total_basis-row['basis_tokens'])/(total_full-row['full_tokens']) for row in rows]
    return ({'full_tokens': total_full, 'basis_tokens': total_basis,
             'reduction_fraction': total_saved/total_full,
             'leave_one_task_min_reduction': min(leave_one),
             'max_task_saved_share': max(row['saved_tokens'] for row in rows)/total_saved,
             'tasks_reduction_at_least_0_50': len(qualifying),
             'anonymous_task_rows': rows}, qualifying)


def calculate(local, full, task_of, raw_lengths):
    scenarios = {}
    qualifying_all_caps = None
    for cap in CAPS:
        label = 'raw' if cap is None else str(cap)
        lengths = {node: raw if cap is None else min(raw, cap) for node, raw in raw_lengths.items()}
        basis = choose_basis(local, full, lengths)
        full_graph, basis_graph, gain_rows = task_gain_rows(local, full, basis, task_of)
        cost, qualifying = cost_stats(full, basis, task_of, lengths)
        qualifying_all_caps = qualifying if qualifying_all_caps is None else qualifying_all_caps & qualifying
        scenarios[label] = {'basis_pairs': len(basis), 'full_rank_gain': full_graph['total_rank_gain'],
                            'basis_rank_gain': basis_graph['total_rank_gain'],
                            'tasks_exact': sum(row['full_gain'] == row['basis_gain'] for row in gain_rows),
                            'per_task_rank_gain_exact': all(row['full_gain'] == row['basis_gain'] for row in gain_rows),
                            **cost}
    all_rank = all(row['per_task_rank_gain_exact'] and row['full_rank_gain'] == row['basis_rank_gain'] == 790
                   for row in scenarios.values())
    gates = {
        'all_caps_per_task_and_total_rank_exact': all_rank,
        'all_caps_token_reduction_at_least_0_60': all(row['reduction_fraction'] >= 0.60 for row in scenarios.values()),
        'all_caps_leave_one_task_reduction_at_least_0_60':
            all(row['leave_one_task_min_reduction'] >= 0.60 for row in scenarios.values()),
        'all_caps_max_task_saved_share_at_most_0_20':
            all(row['max_task_saved_share'] <= 0.20 for row in scenarios.values()),
        'tasks_ge_0_50_in_every_cap_at_least_20_of_28': len(qualifying_all_caps) >= 20,
    }
    return {'filtered_reuse_pairs': len(full), 'tasks': len(next(iter(scenarios.values()))['anonymous_task_rows']),
            'tasks_reduction_at_least_0_50_in_every_cap': len(qualifying_all_caps),
            'scenarios': scenarios, 'gates': gates, 'all_gates_pass': all(gates.values())}


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
    reuse = derive_reuse(local, global_all, run_of, task_of)
    full = record_consistent(reuse, cards, batches)
    local_ids = {node for edge in local for node in edge}
    with LENGTHS[0].open(newline='') as handle:
        raw_lengths = read_raw_lengths(local_ids, list(csv.DictReader(handle)))
    check(len(full) == 2745, 'filtered_count_drift')
    result = calculate(local, full, task_of, raw_lengths)
    for path, digest in [*INPUTS.values(), *EXTRA.values(), LENGTHS]:
        checked(path, digest, scan=False)
    status = ('G_REUSE_MIN_TOKEN_BASIS_COST_ROBUST_ACROSS_CAPS_AND_TASKS' if result['all_gates_pass']
              else 'G_REUSE_MIN_TOKEN_BASIS_COST_NOT_ROBUST')
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
