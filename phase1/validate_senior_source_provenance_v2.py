"""Header-backed producer declarations, with launch and collection dates separate.

Opt-in successor only: never changes or overrides the frozen v1/S0 verdict.
A matching archive header is NOT proof of physical-instance identity, executed
producer commit/configuration, experiment isolation, or effect eligibility.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import tarfile

from phase1 import validate_senior_source_provenance_manifest as legacy

ContractError = legacy.ContractError
PROTOCOL = 'senior-source-provenance-declaration-v2'
FIELDS = legacy.PROVENANCE_FIELDS | {'launch_date', 'producer_instance_id', 'journal_member'}
INSTANCE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{7,159}')


def require(ok, code):
    if not ok:
        raise ContractError(code)


def regular_unlinked(path):
    raw = Path(path).absolute()
    require(not raw.is_symlink() and not any(p.is_symlink() for p in raw.parents), 'symlinked_input')
    result = raw.resolve(strict=True)
    require(result.is_file(), 'nonregular_input')
    return result


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, 'duplicate_json_key')
        out[key] = value
    return out


def read_metadata(path, expected_sha, fields):
    require(isinstance(expected_sha, str) and legacy.SHA256_RE.fullmatch(expected_sha), 'invalid_expected_digest')
    p = regular_unlinked(path)
    require(p.stat().st_size <= 32*1024*1024, 'metadata_too_large')
    raw = p.read_bytes()
    require(not legacy.CREDENTIAL.search(raw), 'credential_shaped_metadata')
    require(hashlib.sha256(raw).hexdigest() == expected_sha, 'metadata_digest_mismatch')
    rows = []
    for line in raw.splitlines():
        require(bool(line.strip()), 'blank_metadata_line')
        row = json.loads(line, object_pairs_hook=strict_object)
        require(isinstance(row, dict) and set(row) == fields, 'metadata_schema_mismatch')
        rows.append(row)
    require(bool(rows), 'empty_metadata')
    return p, rows


def calendar(value):
    require(isinstance(value, str), 'date_must_be_string')
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError('invalid_calendar_date') from exc
    require(parsed.isoformat() == value, 'noncanonical_calendar_date')
    return parsed


def bind_rows(rows, expected):
    require(all(isinstance(r.get('run_id'), str) for r in rows), 'invalid_run_id')
    require([r['run_id'] for r in rows] == sorted(r['run_id'] for r in rows), 'unsorted_run_ids')
    mapped, instances, origins = {}, set(), set()
    for row in rows:
        require(set(row) == FIELDS, 'declaration_schema_mismatch')
        rid = row['run_id']
        require(rid in expected and rid not in mapped, 'unexpected_or_duplicate_run')
        exp = expected[rid]
        require(row['task'] == exp['task'], 'task_mismatch')
        calendar(row['launch_date'])
        require(row['launch_date'] == exp['run_date'], 'launch_date_mismatch')
        source_date = calendar(row['source_date'])
        archive_parts = legacy.safe_relative_parts(row['archive_path'])
        day = source_date.strftime('%m%d')
        require(archive_parts[0] == day or archive_parts[0].startswith(day+'-'), 'collection_directory_date_mismatch')
        # Crucially, there is NO equality requirement between these two dates.
        require(isinstance(row['archive_sha256'], str) and legacy.SHA256_RE.fullmatch(row['archive_sha256']), 'invalid_archive_digest')
        require(isinstance(row['producer_commit'], str) and legacy.GIT_COMMIT_RE.fullmatch(row['producer_commit']), 'invalid_declared_commit')
        instance = row['producer_instance_id']
        require(isinstance(instance, str) and INSTANCE.fullmatch(instance) and instance not in instances, 'invalid_or_reused_instance')
        batch = row['batch_id']
        parts = legacy.safe_relative_parts(batch)
        require(len(parts) == 1, 'invalid_batch_component')
        member_parts = legacy.safe_relative_parts(row['journal_member'])
        require(len(member_parts) >= 4 and member_parts[0] == batch and
                member_parts[-3:] == (exp['source_run_name'], 'checkpoint', 'journal.jsonl'), 'journal_path_not_exactly_bound')
        origin = (row['archive_sha256'], row['journal_member'])
        require(origin not in origins, 'journal_reused_for_multiple_run_ids')
        instances.add(instance); origins.add(origin)
        mapped[rid] = dict(row)
    require(set(mapped) == set(expected), 'expected_run_coverage_incomplete')
    return mapped


def scan_headers(path, digest, wanted):
    before = path.stat()
    require(legacy.sha256_file(path) == digest, 'archive_digest_mismatch')
    hits, headers = Counter(), []
    declared = 0
    with tarfile.open(path, mode='r|*') as archive:
        for member in archive:
            require(len(headers) < 1_000_000 and member.size >= 0, 'archive_resource_cap')
            declared += member.size
            require(declared <= 256*1024**3, 'archive_declared_bytes_cap')
            require(member.isfile() or member.isdir(), 'unsupported_archive_member_type')
            parts = legacy.safe_tar_parts(member.name)
            canonical = '/'.join(parts)
            headers.append((canonical, member.size, 'file' if member.isfile() else 'dir'))
            if canonical in wanted:
                require(member.isfile(), 'journal_not_regular')
                hits[canonical] += 1
    require(all(hits[name] == 1 for name in wanted), 'journal_header_missing_or_duplicated')
    after = path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) ==
            (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns), 'archive_changed')
    require(legacy.sha256_file(path) == digest, 'archive_post_digest_mismatch')
    return {'archive_sha256':digest, 'compressed_bytes':before.st_size, 'headers':len(headers),
            'declared_member_bytes':declared, 'referenced_journals':len(wanted),
            'header_inventory_sha256':hashlib.sha256(legacy.canonical_json(headers).encode()).hexdigest()}


def validate(expected_path, expected_sha, declaration_path, declaration_sha, source_root):
    expected_file, expected_rows = read_metadata(expected_path, expected_sha, legacy.EXPECTED_RUN_FIELDS)
    declaration_file, rows = read_metadata(declaration_path, declaration_sha, FIELDS)
    expected = legacy.validate_expected_runs(expected_rows)
    for item in expected.values():
        calendar(item['run_date'])
    mapped = bind_rows(rows, expected)
    raw_root = Path(source_root).absolute()
    require(not raw_root.is_symlink() and not any(p.is_symlink() for p in raw_root.parents), 'symlinked_archive_root')
    root = raw_root.resolve(strict=True)
    require(root.is_dir(), 'invalid_archive_root')
    by_archive = {}
    for row in mapped.values():
        binding = by_archive.setdefault(row['archive_path'], {'digest':row['archive_sha256'],'members':set()})
        require(binding['digest'] == row['archive_sha256'], 'conflicting_archive_digests')
        binding['members'].add(row['journal_member'])
    archives = [scan_headers(legacy.resolve_archive(root, path), b['digest'], b['members'])
                for path,b in sorted(by_archive.items())]
    require(legacy.sha256_file(expected_file) == expected_sha and legacy.sha256_file(declaration_file) == declaration_sha,
            'metadata_changed_during_validation')
    return {'protocol':PROTOCOL, 'status':'HEADER_BACKED_DECLARATION_ONLY_NOT_EFFECT_ELIGIBLE',
            'inputs':{'expected_runs_sha256':expected_sha,'producer_declaration_sha256':declaration_sha},
            'declaration_mapping_sha256':legacy.rows_sha256([mapped[r] for r in sorted(mapped)]),
            'inventory':{'runs':len(mapped),'tasks':len({r['task'] for r in rows}),'archives':len(archives),
                         'launch_collection_date_differences':sum(r['launch_date'] != r['source_date'] for r in rows)},
            'archives':archives,
            'verified':{'exact_expected_run_coverage':True,'explicit_journal_header_binding':True,
                        'archive_pre_post_hashes':True,'launch_date_matches_run_suffix':True,
                        'collection_month_day_matches_archive_directory':True,'declared_instance_ids_unique':True},
            'not_verified':{'producer_commit_execution_attestation':True,'physical_instance_alias_truth':True,
                            'collection_calendar_date_attestation':True,'exact_producer_config':True,
                            'experiment_closed_split':True,'unreferenced_archive_inventory':True},
            'scope':{'old_S0_overridden':False,'source_ambiguity_automatically_resolved':False,
                     'new_train_pool_created':False,'effect_authorized':False,
                     'tar_member_payloads_opened':False,'cards_or_pairs_opened':False,
                     'model_fit_or_gpu_used':False}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('expected-runs','expect-runs-sha256','provenance-manifest','expect-provenance-sha256','source-root','output'):
        p.add_argument('--'+flag, required=True)
    a = p.parse_args()
    try:
        result = validate(a.expected_runs,a.expect_runs_sha256,a.provenance_manifest,a.expect_provenance_sha256,a.source_root)
        output = Path(a.output)
        require(output.parent.is_dir() and not output.is_symlink() and
                not any(p.is_symlink() for p in output.absolute().parents), 'unsafe_output')
        with output.open('x',encoding='utf-8',newline='\n') as handle:
            handle.write(json.dumps(result,sort_keys=True,indent=2)+'\n')
    except (ContractError,OSError,ValueError,tarfile.TarError):
        print('DECLARATION_V2_FAILED_CLOSED')
        return 2
    print('DECLARATION_V2_HEADER_CHECK_PASS_NOT_EFFECT_ELIGIBLE')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
