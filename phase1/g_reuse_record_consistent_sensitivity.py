"""Sensitivity of G-reuse graph gain to known record defects; no training authorization."""
import hashlib
import json
from pathlib import Path

from phase1.g_reuse_task_breadth import derive_reuse, summarize
from phase1.historical_label_reuse_support import INPUTS, checked, install_guard, pairs, project, check
from phase1.historical_global_local_source_gate import project_cards, project_batches

BASE = Path('/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3/producer_1')
EXTRA = {
    'batches': (BASE/'run_batch_manifest.jsonl',
                '60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'),
    'manifest': (BASE/'sha256_manifest.json',
                 'e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92'),
}


def record_consistent(edges, cards, batches):
    kept = []
    for a, b in edges:
        same_config = cards[a][2] == cards[b][2]
        unique_source = batches[cards[a][0]][1] == batches[cards[b][0]][1] == 'unique'
        if same_config and unique_source:
            kept.append((a, b))
    return kept


def decide(full_metrics, filtered_metrics):
    full_gain = full_metrics['total_rank_gain']
    filtered_gain = filtered_metrics['total_rank_gain']
    check(full_gain > 0, 'nonpositive_full_gain')
    retention = filtered_gain / full_gain
    gates = {
        'rank_gain_retention_at_least_0_80': retention >= 0.80,
        'at_least_20_positive_tasks': filtered_metrics['tasks_with_positive_rank_gain'] >= 20,
        'max_task_gain_share_at_most_0_20': filtered_metrics['max_task_gain_share'] <= 0.20,
    }
    return {
        'full_reuse_pairs': full_metrics['reuse_pairs'],
        'filtered_reuse_pairs': filtered_metrics['reuse_pairs'],
        'full_rank_gain': full_gain,
        'filtered_rank_gain': filtered_gain,
        'rank_gain_retention': retention,
        'tasks': filtered_metrics['tasks'],
        'tasks_with_positive_rank_gain': filtered_metrics['tasks_with_positive_rank_gain'],
        'max_task_rank_gain': filtered_metrics['max_task_rank_gain'],
        'max_task_gain_share': filtered_metrics['max_task_gain_share'],
        'gates': gates,
        'all_gates_pass': all(gates.values()),
        'anonymous_task_rows': filtered_metrics['anonymous_task_rows'],
    }


def main():
    opened = install_guard([p for p, _ in EXTRA.values()])
    for path, digest in [*INPUTS.values(), *EXTRA.values()]:
        checked(path, digest)
    local = pairs([json.loads(line) for line in INPUTS['local'][0].read_text().splitlines()])
    global_all = pairs([json.loads(line) for line in INPUTS['global'][0].read_text().splitlines()])
    grouped = json.loads(INPUTS['cards'][0].read_text())
    run_of, task_of = project(grouped)
    cards = project_cards(grouped)
    batch_rows = [json.loads(line) for line in EXTRA['batches'][0].read_text().splitlines()]
    batches = project_batches(batch_rows)
    check(set(batches) == set(grouped), 'batch_inventory_drift')
    manifest = json.loads(EXTRA['manifest'][0].read_text())
    check(manifest.get('run_batch_manifest.jsonl') == EXTRA['batches'][1], 'manifest_binding_drift')
    reuse = derive_reuse(local, global_all, run_of, task_of)
    filtered = record_consistent(reuse, cards, batches)
    check(len(reuse) == 3058 and len(filtered) == 2745, 'known_edge_count_drift')
    full_metrics = summarize(local, reuse, task_of)
    filtered_metrics = summarize(local, filtered, task_of)
    metrics = decide(full_metrics, filtered_metrics)
    for path, digest in [*INPUTS.values(), *EXTRA.values()]:
        checked(path, digest, scan=False)
    status = ('RECORD_CONSISTENT_G_REUSE_SENSITIVITY_SUPPORTED' if metrics['all_gates_pass']
              else 'RECORD_CONSISTENT_G_REUSE_SENSITIVITY_NOT_SUPPORTED')
    return {
        'status': status,
        'metrics': metrics,
        'input_sha256': {**{k: d for k, (_, d) in INPUTS.items()},
                         **{k: d for k, (_, d) in EXTRA.items()}},
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'data_open_counts': dict(opened),
        'observed_config_is_not_producer_attestation': True,
        'unique_projection_is_not_authoritative_source_repair': True,
        'experiment_closed_split_verified': False,
        'pool_written': False,
        'protected_cohort_files_opened': 0,
        'gpu_jobs': 0,
        'api_calls': 0,
        'model_fits': 0,
    }


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
