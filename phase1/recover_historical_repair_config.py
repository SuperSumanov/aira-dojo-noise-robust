"""Recover only missing historical configs from a separately hashed repair copy.

Does not promote/replace an archive, extract journal/env payloads, or qualify a
training source. Existing S0 holds and all original records are retained.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tarfile
import time

from recover_historical_production_configs import (
    OLD, RUNS_SHA, canonical, config_record, digest, hash_file, load_locked,
    regular, require, safe_parts,
)

CANDIDATE_SHA = '8ade376fb045aa47bffa63b493fa5e4b02d376815d7700c9c9f441c1848edfa4'
CANDIDATE = Path('/tmp/historical-source-repair-download-20260905/candidate-02.tar.gz')
RECOVERY = Path('/research/d7/spc/yzyang4/historical-config-recovery-14f8da6-20260905')
MAPPING_SHA = 'ca49fd3217abc6bd4e66c7f581b2f0b065ae8e22226ebd96c938c93ade58d0fc'


def inspect(path, sha, expected, deadline):
    before = regular(path)
    require(before.st_size < 256 * 1024**2, 'archive_size_cap')
    require(hash_file(path, deadline) == sha, 'candidate_hash_drift')
    names = {rid.rsplit('__', 1)[0] for rid in expected}
    records, header_names, counts = [], set(), Counter()
    with tarfile.open(path, mode='r|*') as archive:
        for member in archive:
            require(time.monotonic() < deadline, 'time_cap')
            counts['headers'] += 1
            counts['declared_bytes'] += max(0, member.size)
            require(counts['headers'] <= 100_000 and counts['declared_bytes'] <= 16 * 1024**3,
                    'member_cap')
            parts = safe_parts(member.name)
            name = '/'.join(parts)
            require(name not in header_names, 'duplicate_member')
            header_names.add(name)
            require(member.isdir() or member.isfile(), 'unsupported_member_type')
            if len(parts) < 2 or not any(part in names for part in parts[:-1]):
                continue
            if parts[-1] == 'journal.jsonl':
                counts['matching_journal_headers'] += 1
            if parts[-1] != 'dojo_config.json' or parts[-2] not in names:
                continue
            require(member.isfile() and 0 < member.size <= 5 * 1024**2, 'config_size_or_type')
            stream = archive.extractfile(member)
            require(stream is not None, 'config_stream')
            raw = stream.read(5 * 1024**2 + 1)
            require(len(raw) == member.size, 'config_length')
            counts['config_payloads_read'] += 1
            record = config_record(raw, sha, name, expected)
            if record is not None:
                records.append(record)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'candidate_changed')
    require(hash_file(path, deadline) == sha, 'candidate_post_hash_drift')
    return records, dict(counts)


def main(output):
    os.umask(0o077)
    require(not output.exists() and not output.is_symlink(), 'output_exists')
    require(output.parent.resolve(strict=True) == output.parent, 'output_parent')
    rows = load_locked(OLD / 'run_batch_manifest.jsonl', RUNS_SHA, True)
    expected = {r['run_id']: r for r in rows}
    require(len(rows) == len(expected) == 676, 'historical_scope')
    previous = load_locked(RECOVERY / 'recovered_mapping.private.json', MAPPING_SHA)
    require(set(previous) <= set(expected) and len(previous) == 668, 'previous_coverage')
    missing = {rid: row for rid, row in expected.items() if rid not in previous}
    require(len(missing) == 8, 'missing_scope')
    output.mkdir(mode=0o700)
    records, counts = inspect(CANDIDATE, CANDIDATE_SHA, missing, time.monotonic() + 300)
    recovered = {}
    for record in records:
        require(record['run_id'] not in recovered, 'multiple_missing_run_configs')
        recovered[record['run_id']] = [record]
    require(set(recovered) <= set(missing), 'outside_scope')
    combined = dict(previous, **recovered)
    raw = canonical(combined)
    (output / 'repair_records.private.json').write_bytes(canonical(records))
    (output / 'combined_mapping.private.json').write_bytes(raw)
    result = dict(
        status='HISTORICAL_REPAIR_CONFIG_EVIDENCE_ONLY',
        candidate_sha256=CANDIDATE_SHA, input_mapping_sha256=MAPPING_SHA,
        expected_runs=len(expected), previously_recovered=len(previous),
        newly_recovered=len(recovered), combined_coverage=len(combined),
        remaining_missing=len(set(expected) - set(combined)),
        counts=counts, combined_mapping_sha256=digest(raw),
        source_sha256=digest(Path(__file__).read_bytes()),
        dependency_sha256=digest(Path(__file__).with_name('recover_historical_production_configs.py').read_bytes()),
        old_S0_overridden=False, old_archives_modified=False,
        journal_env_outcome_payload_reads=0, training_source_qualified=False,
        recorded_runner_commits_present=sum(bool(r['recorded_runner_git_commit']) for r in records),
        recorded_meta_ids_present=sum(bool(r['recorded_meta_id']) for r in records),
    )
    (output / 'summary.json').write_bytes(canonical(result))
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
