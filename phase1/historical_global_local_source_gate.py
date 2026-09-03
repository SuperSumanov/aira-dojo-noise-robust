"""Read-only applicability check of existing provenance to historical L/G inputs.

This does not rerun or override the failed 20260821 S0, repair source identity,
materialize pairs, assign splits, or authorize an effect experiment. Only an
aggregate receipt leaves the process. The old grouped container is parsed but
code, labels, scores and outcomes are not inspected or used by this diagnostic.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from phase1.historical_global_local_pool_readiness import GLOBAL, GLOBAL_SHA, project_pairs
from phase1.historical_train_encoding_readiness import CARDS, TRAIN, EXPECTED, checked_digest

ROOT = Path('/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3/producer_1')
BATCHES = ROOT / 'run_batch_manifest.jsonl'
BATCH_SHA = '60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'
MANIFEST = ROOT / 'sha256_manifest.json'
MANIFEST_SHA = 'e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92'
BASE_COMMIT = '42acf6c328980cf578625e911e2da8b8da9be05a'
CONFIG_FIELDS = ('client', 'hardware', 'time_limit', 'execution_timeout')
BATCH_FIELDS = {'run_id', 'task', 'original_hold', 'source_match_status',
                'source_candidate_batches', 'source_day', 'batch_sha256'}
INPUTS = {TRAIN: EXPECTED[TRAIN], CARDS: EXPECTED[CARDS], GLOBAL: GLOBAL_SHA,
          BATCHES: BATCH_SHA, MANIFEST: MANIFEST_SHA}


def project_cards(grouped):
    result = {}
    if not isinstance(grouped, dict) or not grouped:
        raise ValueError('invalid_grouped_root')
    for run, cards in grouped.items():
        if not isinstance(run, str) or not run or not isinstance(cards, list) or not cards:
            raise ValueError('invalid_grouped_run')
        for card in cards:
            cid, task = card['id'], card['task']['name']
            if not isinstance(cid, str) or not cid or cid in result or not isinstance(task, str) or not task:
                raise ValueError('invalid_card_identity')
            config = tuple(card.get(k) for k in CONFIG_FIELDS)
            encoded = json.dumps(config, sort_keys=True, separators=(',', ':'), allow_nan=False)
            present = tuple(v is not None and v != '' for v in config)
            result[cid] = (run, task, encoded, present)
    return result


def project_batches(rows):
    result = {}
    for row in rows:
        if set(row) != BATCH_FIELDS:
            raise ValueError('unexpected_batch_schema')
        rid, task, state = row['run_id'], row['task'], row['source_match_status']
        count, batch = row['source_candidate_batches'], row['batch_sha256']
        if not isinstance(rid, str) or not rid or rid in result or not isinstance(task, str) or not task:
            raise ValueError('invalid_batch_identity')
        if type(count) is not int or count < 0 or state not in ('unique', 'missing', 'ambiguous'):
            raise ValueError('invalid_batch_status')
        if state == 'unique':
            if count != 1 or not isinstance(batch, str) or re.fullmatch('[0-9a-f]{64}', batch) is None:
                raise ValueError('invalid_unique_batch')
        elif batch is not None or (state == 'missing' and count != 0) or (state == 'ambiguous' and count < 2):
            raise ValueError('invalid_nonunique_batch')
        result[rid] = (task, state, batch)
    return result


def summarize(g, l, cards, batches):
    all_runs = {v[0] for v in cards.values()}
    if all_runs != set(batches):
        raise ValueError('batch_inventory_not_exact')
    if any(v[1] != batches[v[0]][0] for v in cards.values()):
        raise ValueError('batch_task_mismatch')
    local_ids = {x for p in l for x in p}
    if not local_ids <= cards.keys():
        raise ValueError('local_endpoint_missing')
    local_runs = {cards[x][0] for x in local_ids}
    local_pairs = set(l)
    candidate = [(a, b) for a, b in g if a in cards and b in cards
                 and cards[a][1] == cards[b][1] and cards[a][0] in local_runs
                 and cards[b][0] in local_runs and (a, b) not in local_pairs]
    if len(candidate) != len(set(candidate)):
        raise ValueError('duplicate_global_candidate')

    def pool(pairs):
        ids = {x for p in pairs for x in p}
        runs = {cards[x][0] for x in ids}
        counts = collections.Counter()
        for a, b in pairs:
            left, right = cards[a], cards[b]
            if left[1] != right[1]:
                raise ValueError('cross_task_pair')
            same_config = left[2] == right[2]
            counts['equal_observed_config_pairs' if same_config else 'unequal_observed_config_pairs'] += 1
            counts['incomplete_observed_config_pairs'] += int(not all(left[3] + right[3]))
            counts['same_grouped_run_pairs'] += int(left[0] == right[0])
            bl, br = batches[left[0]], batches[right[0]]
            unique = bl[1] == br[1] == 'unique'
            counts['unique_source_pairs' if unique else 'unresolved_source_pairs'] += 1
            if unique:
                counts['same_source_batch_pairs' if bl[2] == br[2] else 'cross_source_batch_pairs'] += 1
        for k in ('equal_observed_config_pairs', 'unequal_observed_config_pairs',
                  'incomplete_observed_config_pairs', 'same_grouped_run_pairs',
                  'unique_source_pairs', 'unresolved_source_pairs',
                  'same_source_batch_pairs', 'cross_source_batch_pairs'):
            counts.setdefault(k, 0)
        return {'rows': len(pairs), 'unique_pairs': len(set(pairs)), 'endpoints': len(ids),
                'runs': len(runs), 'tasks': len({cards[x][1] for x in ids}), **dict(counts),
                'run_source_status': {s: sum(batches[r][1] == s for r in runs)
                                      for s in ('unique', 'ambiguous', 'missing')},
                'endpoint_fields_present': {k: sum(cards[x][3][i] for x in ids)
                                            for i, k in enumerate(CONFIG_FIELDS)}}

    run_configs = collections.defaultdict(set)
    for data in cards.values():
        if data[0] in local_runs:
            run_configs[data[0]].add(data[2])
    inside_batches = {batches[r][2] for r in local_runs if batches[r][1] == 'unique'}
    outside_batches = {batches[r][2] for r in all_runs - local_runs if batches[r][1] == 'unique'}
    shared = inside_batches & outside_batches
    return {'local': pool(l), 'global_candidate': pool(candidate),
            'train_run_metadata_constant': all(len(c) == 1 for c in run_configs.values()),
            'train_runs_with_varying_observed_config': sum(len(c) != 1 for c in run_configs.values()),
            'known_source_batches_in_local_train': len(inside_batches),
            'known_source_batches_shared_with_outside_local_train': len(shared),
            'local_train_runs_in_shared_known_batches': sum(batches[r][2] in shared for r in local_runs),
            'outside_local_train_runs_in_shared_known_batches': sum(batches[r][2] in shared for r in all_runs - local_runs),
            'outside_local_train_is_not_assumed_to_be_dev_or_test': True,
            'exact_producer_config_verified': False, 'experiment_closed_split_verified': False,
            'new_pool_created': False, 'effect_authorized': False}


def install_guard():
    opened = collections.Counter()
    allowed = {p.resolve() for p in INPUTS}
    def guard(event, args):
        if event in ('socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'):
            raise PermissionError('offline_check')
        if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise PermissionError('read_only_check')
        if p in allowed:
            opened[str(p)] += 1
        elif p.suffix.lower() not in ('.py', '.pyc'):
            raise PermissionError('nonallowlisted_read')
    sys.addaudithook(guard)
    return opened


def run():
    opened = install_guard()
    for p, digest in INPUTS.items():
        if p.is_symlink() or not p.is_file():
            raise ValueError('unsafe_input')
        checked_digest(p, digest, scan=True)
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get(BATCHES.name) != BATCH_SHA:
        raise ValueError('upstream_manifest_does_not_bind_batch_file')
    cards = project_cards(json.loads(CARDS.read_text()))
    batches = project_batches([json.loads(line) for line in BATCHES.read_text().splitlines()])
    g, l = project_pairs(GLOBAL.read_text()), project_pairs(TRAIN.read_text())
    metrics = summarize(g, l, cards, batches)
    if len(cards) != 31742 or len(batches) != 676 or len(g) != 14206 or len(l) != 4689 or metrics['global_candidate']['rows'] != 9392:
        raise ValueError('fixed_candidate_reproduction_failed')
    for p, digest in INPUTS.items():
        checked_digest(p, digest)
    return {'status': 'HISTORICAL_SOURCE_APPLICABILITY_ONLY_EFFECT_BLOCKED',
            'base_commit': BASE_COMMIT, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'inputs': {str(p): d for p, d in INPUTS.items()}, 'metrics': metrics,
            'access': {'data_open_counts': dict(opened), 'python_audit_not_os_sandbox': True,
                       'archive_payloads_opened': 0, 'dev_test_vault_files_opened': 0,
                       'code_grade_gap_or_orientation_used': False,
                       'gpu_jobs': 0, 'api_calls': 0, 'model_fits': 0},
            'limitations': ['Observed card metadata equality is not producer-config provenance.',
                            'Prior full S0 failed; subset counts do not override it.',
                            'Outside-local-train runs are not classified as dev/test.',
                            'Global cross-batch pairs are descriptive, not automatically invalid.',
                            'Grouped-run membership is not new proof of physical-run identity.']}


if __name__ == '__main__':
    try:
        print(json.dumps(run(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}))
        raise SystemExit(1)
