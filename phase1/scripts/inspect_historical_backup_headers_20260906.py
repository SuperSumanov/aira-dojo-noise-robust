"""Bounded header-only search of the already fixed 24 historical archives.

No member is extracted, JSON-parsed or printed. Compressed stream traversal
necessarily decompresses/skips payload bytes: this is not a zero-byte OS boundary.
Candidate names are saved only in a private remote receipt, not emitted.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import time

B = Path('/research/d7/spc/yzyang4')
OUT = B / 'historical-backup-header-inventory-20260906'
SECRET = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
DEADLINE = None


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def h(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            require(time.monotonic() < DEADLINE, 'time_cap')
            digest.update(part)
    return digest.hexdigest()


def locked(path, digest, jsonl=False):
    require(path.resolve() == path and path.stat().st_size < 32 * 1024**2, 'metadata_path_or_size')
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == digest and not SECRET.search(raw), 'metadata_binding_or_credential')
    return [json.loads(x) for x in raw.splitlines()] if jsonl else json.loads(raw)


def categories(parts, snapshot_names):
    low = [s.lower() for s in parts]
    name = low[-1]
    results = []
    if name in ('pyproject.toml', 'uv.lock', 'poetry.lock', 'pipfile.lock', 'setup.py', 'setup.cfg') or re.fullmatch(r'(?:requirements[^/]*\.txt|(?:environment|conda)[^/]*\.ya?ml|(?:pip[_-]?freeze|installed[_-]?packages)[^/]*\.(?:txt|json))', name):
        results.append('dependency_or_package_record_header')
    if any(p in snapshot_names for p in parts[:-1]):
        results.append('recorded_snapshot_component_header')
    if any(low[i:i+2] in (['src', 'dojo'], ['src', 'aira_core'], ['mlebench', 'grading']) for i in range(len(low) - 1)):
        results.append('implementation_tree_header')
    if re.search(r'(snapshot|source|code|repo)', name) and name.endswith(('.tar', '.tar.gz', '.tgz', '.zip', '.bundle')):
        results.append('packed_code_backup_header')
    if re.search(r'(runtime|provenance|execution|build)[_-]?(receipt|manifest|identity|versions?)', name) and name.endswith(('.json', '.jsonl', '.txt')):
        results.append('runtime_provenance_header')
    return results


def main():
    global DEADLINE
    start = time.monotonic()
    DEADLINE = start + 300
    require(not OUT.exists(), 'already_attempted_no_overwrite')
    scope = locked(B / 'historical-runtime-prefix-79164e0-20260906-A/runtime_prefix.private.json',
                   'fc13d25745c1c8ea408374741358137e9eb374b3b214e0c9f6d4b856b071464b')
    lineage = locked(B / 'historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json',
                     'fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981')
    selected = set(scope['selected_runs'])
    snapshots = {PurePosixPath(m['identity']['snapshot_path']).name for m in lineage['manifests'] if any(t['run_id'] in selected for t in m['tasks'])}
    expected = {a['archive_sha256'] for a in scope['archives']}
    require(len(selected) == 84 and len(expected) == 24 and len(snapshots) == 24, 'fixed_scope_changed')
    manifests = locked(B / 'senior-true-batch-identity-support/a466888-v3/producer_1/archive_manifest.jsonl',
                       '72b74df7387254afc5ca3ec5d79029e74ae8371faa6216742e63be899419e8fd', True)
    paths = {}
    src = B / 'external/senior_data/mle'
    for row in manifests:
        if row['status'] == 'ok':
            p = PurePosixPath(row['relative_path'])
            require(not p.is_absolute() and '..' not in p.parts, 'archive_relative_path')
            paths[row['sha256']] = src.joinpath(*p.parts)
    paths['8ade376fb045aa47bffa63b493fa5e4b02d376815d7700c9c9f441c1848edfa4'] = Path('/tmp/historical-source-repair-download-20260905/candidate-02.tar.gz')
    require(expected <= set(paths), 'missing_archive_binding')
    observations = []
    total_compressed = 0
    for digest in sorted(expected):
        path = paths[digest]
        require(path.resolve() == path and path.is_file() and not path.is_symlink(), 'archive_alias')
        before = path.stat()
        total_compressed += before.st_size
        require(before.st_size <= 512 * 1024**2 and total_compressed <= 5 * 1024**3, 'compressed_cap')
        require(h(path) == digest, 'archive_pre_hash')
        seen = set()
        counts = Counter()
        candidates = []
        header_hash = hashlib.sha256()
        declared = 0
        with tarfile.open(path, mode='r|*') as arc:
            for member in arc:
                require(time.monotonic() < DEADLINE, 'time_cap')
                require(not SECRET.search(member.name.encode()), 'header_credential_withheld')
                p = PurePosixPath(member.name)
                require(not p.is_absolute() and '..' not in p.parts and p.parts and '\\' not in member.name and '\x00' not in member.name, 'unsafe_header')
                name = '/'.join(p.parts)
                require(name not in seen and (member.isdir() or member.isfile()), 'duplicate_or_unsafe_type')
                seen.add(name)
                declared += max(0, member.size)
                require(len(seen) <= 1_000_000 and declared <= 256 * 1024**3, 'declared_cap')
                record = [name, member.size, 'file' if member.isfile() else 'directory']
                header_hash.update(json.dumps(record, separators=(',', ':')).encode() + b'\n')
                if member.isfile():
                    cls = categories(p.parts, snapshots)
                    counts.update(cls)
                    if cls:
                        candidates.append(dict(member=name, declared_bytes=member.size, categories=cls))
        after = path.stat()
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'archive_changed')
        require(h(path) == digest, 'archive_post_hash')
        observations.append(dict(archive_sha256=digest, compressed_bytes=before.st_size, member_headers=len(seen),
                                 header_inventory_sha256=header_hash.hexdigest(), candidate_counts=dict(counts), candidates=candidates))
    counts = Counter()
    for row in observations:
        counts.update(row['candidate_counts'])
    private = json.dumps(observations, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    report = dict(status='FIXED_HISTORICAL_BACKUP_HEADERS_INSPECTED_NOT_PROVENANCE_ATTESTATION',
                  selected_historical_runs=84, archives=24, compressed_bytes=total_compressed,
                  member_headers=sum(r['member_headers'] for r in observations),
                  archives_with_candidate_headers=sum(bool(r['candidates']) for r in observations),
                  candidate_header_counts=dict(counts), payloads_extracted_or_parsed=0,
                  member_names_printed=False, protected_cohort_reads=0, training_source_qualified=False,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  private_inventory_sha256=hashlib.sha256(private).hexdigest(),
                  elapsed_seconds=time.monotonic() - start,
                  scope='fixed 24 archives only; path signatures are not an exhaustive guarantee that no backup exists anywhere',
                  stream_boundary='gzip traversal decompresses/skips member bytes; no zero-byte OS-isolation claim')
    OUT.mkdir(mode=0o700)
    with (OUT / 'header_inventory.private.json').open('xb') as f:
        f.write(private)
    with (OUT / 'summary.json').open('x') as f:
        json.dump(report, f, sort_keys=True, indent=2)
    for p in OUT.iterdir():
        p.chmod(0o400)
    OUT.chmod(0o500)
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    os.umask(0o077)
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'BACKUP_HEADER_INSPECTION_FAILED_CLOSED', 'reason': str(exc) if type(exc) is RuntimeError else type(exc).__name__}))
        raise SystemExit(1)
