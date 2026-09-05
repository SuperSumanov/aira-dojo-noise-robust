"""Build a complete recorded-source ledger, not a qualified training bundle.

All fixed historical runs remain represented. Config payloads are credential
screened and hash-bound; journals are only inspected as headers except duplicate
origins, whose opaque bytes are hashed to check copying (never JSON-parsed).
Recorded fields do not attest pristine execution or server-model immutability.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time

from recover_historical_production_configs import (
    ARCHIVES_SHA, OLD, SOURCE, SECRET, canonical, digest, hash_file, load_locked,
    pairs_object, regular, require, safe_parts,
)
from recover_historical_repair_config import CANDIDATE, CANDIDATE_SHA

MAPPING = Path('/research/d7/spc/yzyang4/historical-repair-config-3044f0a-20260905-A/combined_mapping.private.json')
MAPPING_SHA = 'fd8e0769f4561937f2959c055da18120e3715aaf3b772364cca72e1a4268aec6'


def config_stratum(cfg):
    # Only these instance-output locations are removed. Prompt/client settings,
    # resource limits, task input paths and interpreter image remain included.
    solver = {k: v for k, v in cfg['solver'].items() if k not in ('exp_name', 'checkpoint_path')}
    interpreter = {k: v for k, v in cfg['interpreter'].items() if k != 'working_dir'}
    task = {k: v for k, v in cfg['task'].items() if k != 'results_output_dir'}
    return digest(canonical({'recorded_commit': cfg['metadata']['git_commit_id'],
                             'solver': solver, 'interpreter': interpreter, 'task': task}))


def stream_fingerprint(stream, size, deadline):
    require(0 < size <= 512 * 1024**2, 'journal_size_cap')
    h, n, tail = hashlib.sha256(), 0, b''
    while True:
        require(time.monotonic() < deadline, 'deadline')
        block = stream.read(min(1024**2, size + 1 - n))
        if not block:
            break
        n += len(block)
        require(n <= size and not SECRET.search(tail + block), 'journal_length_or_credential_shape')
        h.update(block)
        tail = (tail + block)[-4096:]
    require(n == size, 'journal_truncated')
    return h.hexdigest()


def scan(path, sha, wanted, duplicate_ids, deadline):
    before = regular(path)
    require(hash_file(path, deadline) == sha, 'archive_pre_hash')
    journals = {str(Path(name).parent / 'checkpoint/journal.jsonl'): rid for name, (rid, _) in wanted.items()}
    require(len(journals) == len(wanted), 'journal_origin_alias')
    seen, configs, headers, fingerprints = set(), {}, {}, {}
    declared = 0
    with tarfile.open(path, 'r|*') as arc:
        for member in arc:
            require(time.monotonic() < deadline, 'deadline')
            name = '/'.join(safe_parts(member.name))
            require(name not in seen and (member.isdir() or member.isfile()), 'duplicate_or_unsafe_member')
            seen.add(name)
            declared += max(0, member.size)
            require(len(seen) <= 1_000_000 and declared <= 256 * 1024**3, 'archive_cap')
            if name in wanted:
                rid, expected_sha = wanted[name]
                require(member.isfile() and 0 < member.size <= 5 * 1024**2, 'config_size_or_type')
                raw = arc.extractfile(member).read(5 * 1024**2 + 1)
                require(len(raw) == member.size and digest(raw) == expected_sha, 'config_hash')
                require(not SECRET.search(raw), 'config_credential_shape')
                cfg = json.loads(raw, object_pairs_hook=pairs_object)
                require(cfg['id'] + '__' + cfg['metadata']['launch_time'][:10] == rid, 'config_run_binding')
                configs[rid] = dict(recorded_config_stratum_sha256=config_stratum(cfg),
                                    recorded_seed=cfg['metadata'].get('seed'),
                                    recorded_execution_id_present=bool(cfg['metadata'].get('execution_id')),
                                    recorded_execution_host_present=bool(cfg['metadata'].get('execution_host')),
                                    recorded_gpu_uuids_present=bool(cfg['metadata'].get('gpu_uuids')))
            if name in journals:
                rid = journals[name]
                require(member.isfile() and member.size > 0, 'journal_missing_or_empty')
                headers[rid] = dict(journal_member=name, journal_bytes=member.size)
                if rid in duplicate_ids:
                    fingerprints[rid] = stream_fingerprint(arc.extractfile(member), member.size, deadline)
    require(set(configs) == set(headers) == {rid for rid, _ in wanted.values()}, 'incomplete_archive_support')
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'archive_changed')
    require(hash_file(path, deadline) == sha, 'archive_post_hash')
    return {'archive_sha256': sha, 'configs': configs, 'journals': headers, 'duplicate_journal_hashes': fingerprints}


def components(mapping):
    parent = {rid: rid for rid in mapping}
    def find(rid):
        while parent[rid] != rid:
            parent[rid] = parent[parent[rid]]
            rid = parent[rid]
        return rid
    shared = {}
    for rid, rows in sorted(mapping.items()):
        for row in rows:
            for key in (('archive_batch', row['archive_sha256'], row['config_member'].split('/')[0]),
                        ('recorded_meta_id', row['recorded_meta_id'])):
                require(key[-1] is not None, 'grouping_identity_missing')
                if key in shared:
                    parent[find(rid)] = find(shared[key])
                else:
                    shared[key] = rid
    groups = defaultdict(list)
    for rid in sorted(mapping):
        groups[find(rid)].append(rid)
    return sorted(groups.values())


def origin_index(mapping):
    wanted = defaultdict(dict)
    for rid, rows in mapping.items():
        for row in rows:
            bucket = wanted[row['archive_sha256']]
            binding = (rid, row['config_sha256'])
            old = bucket.get(row['config_member'])
            require(old is None or old == binding, 'conflicting_config_origin')
            # Same compressed bytes + exact member + config hash is an observed
            # archive copy, not a second independent run. Keep all rows in ledger.
            bucket[row['config_member']] = binding
    return wanted


def build(output):
    os.umask(0o077)
    require(not output.exists() and output.parent.resolve(strict=True) == output.parent, 'output_exists_or_parent')
    mapping = load_locked(MAPPING, MAPPING_SHA)
    require(len(mapping) == 676, 'fixed_run_scope')
    archive_rows = load_locked(OLD / 'archive_manifest.jsonl', ARCHIVES_SHA, True)
    paths = defaultdict(list)
    for row in archive_rows:
        if row['status'] == 'ok':
            paths[row['sha256']].append(SOURCE.joinpath(*safe_parts(row['relative_path'])))
    paths[CANDIDATE_SHA].append(CANDIDATE)
    wanted = origin_index(mapping)
    duplicates = {rid for rid, rows in mapping.items()
                  if len({(r['archive_sha256'], r['config_member']) for r in rows}) > 1}
    for rid, rows in mapping.items():
        for row in rows:
            require(row['archive_sha256'] in paths, 'unknown_archive')
    output.mkdir(mode=0o700)
    deadline = time.monotonic() + 1500
    def work(item):
        sha, wanted_rows = item
        for source_path in paths[sha]:
            regular(source_path)
            require(hash_file(source_path, deadline) == sha, 'physical_archive_copy_hash_drift')
        result = scan(sorted(paths[sha])[0], sha, wanted_rows, duplicates, deadline)
        result['physical_archive_copies_verified'] = len(paths[sha])
        (output / ('archive-' + sha + '.private.json')).write_bytes(canonical(result))
        return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(work, sorted(wanted.items())))
    per_archive = {r['archive_sha256']: r for r in results}
    fingerprints = defaultdict(set)
    ledger = {}
    for rid, rows in sorted(mapping.items()):
        origins = []
        for row in rows:
            source = per_archive[row['archive_sha256']]
            origin = dict(row, **source['configs'][rid], **source['journals'][rid])
            fingerprint = source['duplicate_journal_hashes'].get(rid)
            if fingerprint:
                fingerprints[rid].add(fingerprint)
                origin['opaque_journal_sha256'] = fingerprint
            origins.append(origin)
        require(len({r['recorded_config_stratum_sha256'] for r in origins}) == 1, 'stratum_conflict')
        ledger[rid] = {'origins': origins}
    require(set(fingerprints) == duplicates and all(len(s) == 1 for s in fingerprints.values()),
            'duplicate_journal_copy_conflict')
    grouped = components(mapping)
    role_counts, group_roles = Counter(), Counter()
    for group in grouped:
        blocked = any(mapping[rid][0]['original_hold'] for rid in group)
        group_id = digest(canonical(group))
        for rid in group:
            ledger[rid]['conservative_component_sha256'] = group_id
            ledger[rid]['old_hold_closure_blocks_train'] = blocked
            role_counts['old_hold_closure_blocked' if blocked else 'old_hold_closure_clear_not_admitted'] += 1
        group_roles['old_hold_closure_blocked' if blocked else 'old_hold_closure_clear_not_admitted'] += 1
    raw = canonical(ledger)
    (output / 'source_ledger.private.json').write_bytes(raw)
    strata = Counter(r['origins'][0]['recorded_config_stratum_sha256'] for r in ledger.values())
    summary = dict(status='COMPLETE_RECORDED_SOURCE_LEDGER_NOT_TRAINING_ADMISSION',
        input_mapping_sha256=MAPPING_SHA, ledger_sha256=digest(raw), runs=len(ledger),
        config_journal_origin_bindings=sum(len(r['origins']) for r in ledger.values()),
        referenced_archive_hashes=len(wanted), verified_duplicate_run_copies=len(duplicates),
        identical_archive_member_copy_runs=sum(len(rows)>1 for rid, rows in mapping.items() if rid not in duplicates),
        physical_archive_copies_verified=sum(r['physical_archive_copies_verified'] for r in results),
        duplicate_journal_payloads_opaquely_hashed=sum(len(mapping[rid]) for rid in duplicates),
        old_error_archives_not_silently_reclassified=2, old_S0_overridden=False,
        conservative_components=len(grouped), run_old_hold_closure=dict(role_counts),
        component_old_hold_closure=dict(group_roles), recorded_config_strata=len(strata),
        largest_recorded_config_stratum=max(strata.values()),
        actual_experiment_instance_attested=False, pristine_execution_attested=False,
        journal_outcome_fields_parsed=0, env_payload_reads=0, protected_cohort_reads=0,
        cards_pairs_built=False, training_source_qualified=False,
        source_sha256=digest(Path(__file__).read_bytes()))
    (output / 'summary.json').write_bytes(canonical(summary))
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
