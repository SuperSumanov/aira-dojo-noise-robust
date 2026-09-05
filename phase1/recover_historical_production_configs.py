"""Recover existing historical runner records, without constructing a train set.

Only exact-hash historical archives admitted by the old inventory are opened.
Only dojo_config.json members whose run-directory name appears in the fixed
historical run list are parsed, after credential screening. Journal, env and
outcome members are never extracted. Old error archives remain explicit gaps.
Mappings and config fingerprints stay private on the remote host. This is not
an executed-clean-code attestation and does not override the failed old S0.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import time

OLD = Path('/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3/producer_1')
SOURCE = Path('/research/d7/spc/yzyang4/external/senior_data/mle')
MANIFEST_SHA = 'e313c794d772a5ef058df6afe55f1aed35c695ac236960a9e3dd2a2701989e92'
ARCHIVES_SHA = '72b74df7387254afc5ca3ec5d79029e74ae8371faa6216742e63be899419e8fd'
RUNS_SHA = '60846a3a68f4cc9644ad676aa89e0d250b5fb8c0a3b8f6c1a708f2b5d0fb3e4d'
SECRET = re.compile(
    rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|'
    rb'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|'
    rb'hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{30,}|'
    rb'Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)'
)


class RecoveryError(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise RecoveryError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode() + b'\n'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    require(path.resolve(strict=True) == path and path.is_file() and not path.is_symlink(), 'unsafe_file')
    return path.stat()


def hash_file(path, deadline):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(4 * 1024**2), b''):
            require(time.monotonic() < deadline, 'recovery_time_cap')
            h.update(chunk)
    return h.hexdigest()


def pairs_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate_json_key')
        value[key] = item
    return value


def load_locked(path, sha, jsonl=False):
    st = regular(path)
    require(st.st_size < 32 * 1024**2, 'metadata_size_cap')
    raw = path.read_bytes()
    require(digest(raw) == sha, 'metadata_drift')
    require(not SECRET.search(raw), 'metadata_credential_shape')
    if jsonl:
        return [json.loads(line, object_pairs_hook=pairs_object) for line in raw.splitlines()]
    return json.loads(raw, object_pairs_hook=pairs_object)


def safe_parts(name):
    require(isinstance(name, str) and '\\' not in name and '\x00' not in name, 'unsafe_member_name')
    p = PurePosixPath(name)
    require(not p.is_absolute() and '..' not in p.parts and bool(p.parts), 'unsafe_member_path')
    return p.parts


def config_record(raw, archive_sha, member, expected_runs):
    require(not SECRET.search(raw), 'config_credential_shape')
    obj = json.loads(raw, object_pairs_hook=pairs_object)
    require(isinstance(obj, dict), 'config_not_object')
    metadata = obj.get('metadata')
    require(isinstance(metadata, dict), 'metadata_missing')
    cid, launch = obj.get('id'), metadata.get('launch_time')
    require(isinstance(cid, str) and isinstance(launch, str), 'identity_fields_missing')
    require(re.match(r'^\d{4}-\d{2}-\d{2}[ T]', launch) is not None, 'launch_format')
    dt.datetime.fromisoformat(launch)
    rid = cid + '__' + launch[:10]
    if rid not in expected_runs:
        return None
    task = obj.get('task')
    require(isinstance(task, dict) and task.get('name') == expected_runs[rid]['task'], 'config_task_mismatch')
    require(safe_parts(member)[-2] == cid, 'config_directory_id_mismatch')
    solver, interpreter = obj.get('solver'), obj.get('interpreter')
    require(isinstance(solver, dict) and bool(solver) and isinstance(interpreter, dict), 'resolved_config_missing')
    projected = {k: v for k, v in solver.items() if k not in ('exp_name', 'checkpoint_path')}
    commit = metadata.get('git_commit_id')
    good_commit = isinstance(commit, str) and re.fullmatch('[0-9a-f]{40}', commit) is not None
    meta = obj.get('meta_id')
    meta = meta if isinstance(meta, str) and meta else None
    slurm = metadata.get('slurm_id')
    slurm = str(slurm) if slurm is not None and str(slurm) else None
    return dict(
        run_id=rid, archive_sha256=archive_sha, config_member=member,
        config_sha256=digest(raw), recorded_launch_time=launch,
        recorded_runner_git_commit=commit if good_commit else None,
        recorded_meta_id=meta, recorded_slurm_id=slurm,
        recorded_base_path=metadata.get('base_path'),
        solver_projection_sha256=digest(canonical(projected)),
        task_config_sha256=digest(canonical(task)),
        interpreter_config_sha256=digest(canonical(interpreter)),
        recorded_script_id_present=bool(metadata.get('script_id')),
        original_hold=expected_runs[rid]['original_hold'],
    )


def scan_one(index, row, expected_runs, expected_names, output, deadline):
    result = {'archive_ordinal': index, 'old_status': row['status'], 'records': []}
    if row['status'] != 'ok':
        result.update(status='OLD_ARCHIVE_ERROR_NOT_OPENED', config_members_read=0)
        return result
    configs_read = 0
    try:
        parts = safe_parts(row['relative_path'])
        path = SOURCE.joinpath(*parts)
        before = regular(path)
        require(before.st_size == row['size'], 'archive_size_drift')
        require(hash_file(path, deadline) == row['sha256'], 'archive_hash_drift')
        seen, members, declared = set(), 0, 0
        with tarfile.open(path, mode='r|*') as archive:
            for member in archive:
                require(time.monotonic() < deadline, 'recovery_time_cap')
                members += 1
                declared += max(0, member.size)
                require(members <= 1_000_000 and declared <= 256 * 1024**3, 'archive_resource_cap')
                p = safe_parts(member.name)
                require(member.isdir() or member.isfile(), 'unsupported_member_type')
                if len(p) < 2 or p[-1] != 'dojo_config.json' or p[-2] not in expected_names:
                    continue
                name = '/'.join(p)
                require(name not in seen and member.isfile(), 'duplicate_or_nonfile_config_member')
                seen.add(name)
                require(0 < member.size <= 5 * 1024**2, 'config_size_cap')
                stream = archive.extractfile(member)
                require(stream is not None, 'config_stream_missing')
                raw = stream.read(5 * 1024**2 + 1)
                require(len(raw) == member.size, 'config_size_mismatch')
                configs_read += 1
                record = config_record(raw, row['sha256'], name, expected_runs)
                if record is not None:
                    result['records'].append(record)
        after = path.stat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'archive_changed')
        require(hash_file(path, deadline) == row['sha256'], 'archive_post_hash_drift')
        result.update(status='CONFIG_RECORDS_RECOVERED', member_headers=members)
    except Exception as exc:
        # Retain partial evidence privately, but no record from this archive may
        # participate in the recovered mapping or be treated as an eligible input.
        result.update(status='FAILED_CLOSED', reason=str(exc) if isinstance(exc, RecoveryError)
                      else type(exc).__name__)
    result['config_members_read'] = configs_read
    with (output / f'archive-{index:03d}.private.json').open('xb') as handle:
        handle.write(canonical(result))
    return result


def recover(output, seconds):
    os.umask(0o077)
    require(60 <= seconds <= 1500, 'time_budget')
    require(not output.exists() and not output.is_symlink(), 'output_exists')
    require(output.parent.resolve() == output.parent, 'unsafe_output_parent')
    lock = load_locked(OLD / 'sha256_manifest.json', MANIFEST_SHA)
    require(lock['archive_manifest.jsonl'] == ARCHIVES_SHA and lock['run_batch_manifest.jsonl'] == RUNS_SHA,
            'upstream_manifest_binding')
    archives = load_locked(OLD / 'archive_manifest.jsonl', ARCHIVES_SHA, True)
    runs = load_locked(OLD / 'run_batch_manifest.jsonl', RUNS_SHA, True)
    require(len(archives) == 146 and len(runs) == 676, 'input_count_drift')
    expected = {r['run_id']: r for r in runs}
    require(len(expected) == len(runs), 'duplicate_expected_run')
    require(all(dt.date.fromisoformat(r.rsplit('__', 1)[1]) <= dt.date(2026, 8, 15)
                for r in expected), 'outside_frozen_historical_dates')
    names = {r.rsplit('__', 1)[0] for r in expected}
    output.mkdir(mode=0o700)
    started = time.monotonic()
    deadline = started + seconds
    context = dict(protocol='historical-production-config-recovery-v1',
                   source_sha256=digest(Path(__file__).read_bytes()), archive_manifest_sha256=ARCHIVES_SHA,
                   runs_manifest_sha256=RUNS_SHA, seconds_cap=seconds, workers=2,
                   started_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    (output / 'context.json').write_bytes(canonical(context))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: scan_one(*args, expected, names, output, deadline), enumerate(archives)))
    mapped = defaultdict(list)
    for result in results:
        if result['status'] == 'CONFIG_RECORDS_RECOVERED':
            for record in result['records']:
                mapped[record['run_id']].append(record)
    coverage = Counter()
    tracking = Counter()
    for rid in sorted(expected):
        records = mapped.get(rid, [])
        coverage['with_config' if records else 'without_config'] += 1
        coverage['multiple_config_occurrences'] += len(records) > 1
        if records:
            # Count evidence, not a declaration that identical copies are one run.
            signatures = {(r['recorded_launch_time'], r['recorded_slurm_id'], r['recorded_meta_id'],
                           r['recorded_runner_git_commit'], r['solver_projection_sha256'],
                           r['task_config_sha256'], r['interpreter_config_sha256']) for r in records}
            coverage['tracking_signature_consistent' if len(signatures) == 1 else 'tracking_signature_conflict'] += 1
            for field in ('recorded_runner_git_commit', 'recorded_meta_id', 'recorded_slurm_id'):
                tracking[field + '_present_all_occurrences'] += all(r[field] is not None for r in records)
    mapping_bytes = canonical(dict(sorted(mapped.items())))
    (output / 'recovered_mapping.private.json').write_bytes(mapping_bytes)
    summary = dict(context, status='HISTORICAL_CONFIG_RECOVERY_NOT_TRAINING_ADMISSION',
                   archives=len(archives), expected_runs=len(runs), archive_status=dict(Counter(r['status'] for r in results)),
                   coverage=dict(coverage), tracking=dict(tracking),
                   config_members_read=sum(r['config_members_read'] for r in results),
                   recovered_mapping_sha256=digest(mapping_bytes), elapsed_seconds=time.monotonic() - started,
                   journal_env_outcome_member_reads=0, protected_cohort_reads=0,
                   training_source_qualified=False, old_S0_overridden=False,
                   gpu_jobs=0, api_calls=0, model_fits=0)
    (output / 'summary.json').write_bytes(canonical(summary))
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=1500)
    args = parser.parse_args()
    recover(args.output, args.seconds)
