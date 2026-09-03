"""Independent set-based reconstruction; does not import the source-gate producer."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys

from phase1.historical_train_encoding_readiness import checked_digest

ROOT = Path('/research/d7/spc/yzyang4')
PATHS = {
    'local': (ROOT / 'critic-decision-component-prep/305355e-baf6bdd-v1/producer_1/train.jsonl', '0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e'),
    'global': (Path('/tmp/global-hash-hardened-20260823.9ntGvq/global_train.jsonl'), 'd9163bbcde70d8fe1f6f2ead9db266eca7ced932682cdaed9d3a9ece6fa43010'),
    'cards': (ROOT / 'worktrees/senior_augmented_92a9651_nosmudge/data/augmented_mle_critic/augmented_cards_current.json', '5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb'),
    'batches': (ROOT / 'senior-true-batch-identity-support/a466888-v3/producer_1/run_batch_manifest.jsonl', '60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'),
    'manifest': (ROOT / 'senior-true-batch-identity-support/a466888-v3/producer_1/sha256_manifest.json', 'e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92'),
}
FIELDS = ('client', 'hardware', 'time_limit', 'execution_timeout')


def recompute(grouped, batch_rows, global_rows, local_rows):
    run_of, task_of, config_of, presence = {}, {}, {}, {}
    for run in sorted(grouped):
        for card in grouped[run]:
            cid = card['id']
            if cid in run_of:
                raise ValueError('duplicate_card')
            run_of[cid], task_of[cid] = run, card['task']['name']
            config_of[cid] = json.dumps([card.get(k) for k in FIELDS], sort_keys=True, separators=(',', ':'), allow_nan=False)
            presence[cid] = {k for k in FIELDS if card.get(k) is not None and card.get(k) != ''}
    batches = {row['run_id']: row for row in batch_rows}
    if len(batches) != len(batch_rows) or set(batches) != set(grouped):
        raise ValueError('invalid_batch_inventory')
    if any(task_of[cid] != batches[run]['task'] for cid, run in run_of.items()):
        raise ValueError('task_join_mismatch')
    projected = {}
    for name, rows in (('local', local_rows), ('global', global_rows)):
        if any(row['intask_split'] != 'train' for row in rows):
            raise ValueError('nontrain')
        projected[name] = [tuple(sorted([row['better'], row['worse']])) for row in rows]
        if any(a == b for a, b in projected[name]):
            raise ValueError('self_pair')
    local_runs = {run_of[cid] for pair in projected['local'] for cid in pair}
    train_cards = {cid for cid, run in run_of.items() if run in local_runs}
    candidates = set(projected['global']) - set(projected['local'])
    candidates = {p for p in candidates if set(p) <= train_cards}
    candidates = {p for p in candidates if task_of[p[0]] == task_of[p[1]]}
    occurrences = Counter(projected['global'])
    if any(occurrences[p] != 1 for p in candidates):
        raise ValueError('duplicate_global_candidate')
    unique_runs = {r for r, row in batches.items() if row['source_match_status'] == 'unique'}
    batch_of = {r: row['batch_sha256'] for r, row in batches.items()}

    def pool(pairs):
        endpoints = set().union(*(set(p) for p in pairs))
        runs = {run_of[x] for x in endpoints}
        complete = {i for i, pair in enumerate(pairs) if {run_of[x] for x in pair} <= unique_runs}
        same = {i for i in complete if batch_of[run_of[pairs[i][0]]] == batch_of[run_of[pairs[i][1]]]}
        equal_config = {i for i, (a, b) in enumerate(pairs) if config_of[a] == config_of[b]}
        incomplete_config = {i for i, (a, b) in enumerate(pairs) if presence[a] & presence[b] != set(FIELDS)}
        if any(task_of[a] != task_of[b] for a, b in pairs):
            raise ValueError('cross_task_pair')
        return {'rows': len(pairs), 'unique_pairs': len(set(pairs)), 'endpoints': len(endpoints),
                'runs': len(runs), 'tasks': len({task_of[x] for x in endpoints}),
                'equal_observed_config_pairs': len(equal_config),
                'unequal_observed_config_pairs': len(pairs) - len(equal_config),
                'incomplete_observed_config_pairs': len(incomplete_config),
                'same_grouped_run_pairs': sum(run_of[a] == run_of[b] for a, b in pairs),
                'unique_source_pairs': len(complete), 'unresolved_source_pairs': len(pairs) - len(complete),
                'same_source_batch_pairs': len(same), 'cross_source_batch_pairs': len(complete - same),
                'run_source_status': {s: len(runs & {r for r in batches if batches[r]['source_match_status'] == s})
                                      for s in ('unique', 'ambiguous', 'missing')},
                'endpoint_fields_present': {k: len(endpoints & {x for x in presence if k in presence[x]}) for k in FIELDS}}

    by_batch = defaultdict(set)
    for run in unique_runs:
        by_batch[batch_of[run]].add(run)
    mixed = [rs for rs in by_batch.values() if rs & local_runs and rs - local_runs]
    configs_by_run = defaultdict(set)
    for cid in train_cards:
        configs_by_run[run_of[cid]].add(config_of[cid])
    varying = sum(len(values) > 1 for values in configs_by_run.values())
    return {'local': pool(projected['local']), 'global_candidate': pool(sorted(candidates)),
            'train_run_metadata_constant': varying == 0,
            'train_runs_with_varying_observed_config': varying,
            'known_source_batches_in_local_train': sum(bool(rs & local_runs) for rs in by_batch.values()),
            'known_source_batches_shared_with_outside_local_train': len(mixed),
            'local_train_runs_in_shared_known_batches': sum(len(rs & local_runs) for rs in mixed),
            'outside_local_train_runs_in_shared_known_batches': sum(len(rs - local_runs) for rs in mixed),
            'outside_local_train_is_not_assumed_to_be_dev_or_test': True,
            'exact_producer_config_verified': False, 'experiment_closed_split_verified': False,
            'new_pool_created': False, 'effect_authorized': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--expect-receipt-sha256', required=True)
    args = parser.parse_args()
    allowed = {p.resolve() for p, _ in PATHS.values()} | {args.receipt.resolve()}
    opened = Counter()
    def guard(event, params):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise PermissionError('offline_check')
        if event != 'open' or not isinstance(params[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(params[0])).resolve()
        mode, flags = params[1:3]
        if (isinstance(mode, str) and any(x in mode for x in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise PermissionError('read_only_check')
        if path in allowed:
            opened[str(path)] += 1
        elif path.suffix.lower() not in ('.py', '.pyc'):
            raise PermissionError('unlisted_data')
    sys.addaudithook(guard)
    for p, digest in [*PATHS.values(), (args.receipt, args.expect_receipt_sha256)]:
        if p.is_symlink() or not p.is_file():
            raise ValueError('unsafe_input')
        checked_digest(p, digest, scan=True)
    payload = json.loads(args.receipt.read_text())
    if payload['status'] != 'HISTORICAL_SOURCE_APPLICABILITY_ONLY_EFFECT_BLOCKED':
        raise ValueError('unexpected_status')
    if payload['inputs'] != {str(p): digest for p, digest in PATHS.values()}:
        raise ValueError('input_binding_mismatch')
    raw = {k: p.read_text() for k, (p, _) in PATHS.items()}
    if json.loads(raw['manifest']).get('run_batch_manifest.jsonl') != PATHS['batches'][1]:
        raise ValueError('upstream_binding_mismatch')
    metrics = recompute(json.loads(raw['cards']), [json.loads(x) for x in raw['batches'].splitlines()],
                        [json.loads(x) for x in raw['global'].splitlines()], [json.loads(x) for x in raw['local'].splitlines()])
    if metrics != payload['metrics']:
        raise ValueError('independent_metrics_mismatch')
    for p, digest in [*PATHS.values(), (args.receipt, args.expect_receipt_sha256)]:
        checked_digest(p, digest)
    print(json.dumps({'status': 'INDEPENDENT_SOURCE_APPLICABILITY_VERIFIED_NOT_EFFECT_ELIGIBLE',
                      'receipt_sha256': args.expect_receipt_sha256,
                      'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      'metrics': metrics, 'data_open_counts': dict(opened),
                      'archive_dev_test_vault_files_opened': 0, 'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}))
        raise SystemExit(1)
