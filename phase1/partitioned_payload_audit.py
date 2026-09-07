"""Small fail-closed ledger for an authenticated, caller-owned payload audit.

No tensor loader, network, training, scheduler, or data reader. A completed
part is not a completed audit: the finalizer must rehash every input file.
"""
import hashlib
import json
import math
import os
from pathlib import Path

PARTS = (('prefix1', 0), ('prefix1', 1), ('resume2', 0), ('resume2', 1))
ROLES = ('adamw', 'master_shards', 'numpy_rng', 'python_rng', 'scaler', 'torch_rng')


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def part_name(case, rank):
    require(type(rank) is int and (case, rank) in PARTS, 'invalid_partition')
    return f'{case}-rank{rank}'


def payload_names(rank):
    require(type(rank) is int and rank in (0, 1), 'invalid_rank')
    return (f'pytorch_model/zero_pp_rank_{rank}_mp_rank_00_model_states.pt',
            f'pytorch_model/bf16_zero_pp_rank_{rank}_mp_rank_00_optim_states.pt',
            f'random_states_{rank}.pkl')


def unique(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate_json_field')
        result[key] = value
    return result


def fingerprint(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path
            and not any(p.is_symlink() for p in (path, *path.parents))
            and path.is_file(), 'unsafe_part_file')
    s = path.stat()
    require(s.st_nlink == 1 and not s.st_mode & 0o222, 'unsealed_part_file')
    if hasattr(s, 'st_uid') and hasattr(os, 'getuid'):
        require(s.st_uid == os.getuid(), 'unowned_part_file')
    return dict(dev=s.st_dev, inode=s.st_ino, bytes=s.st_size,
                mtime_ns=s.st_mtime_ns, ctime_ns=s.st_ctime_ns)


def verified_file(path, expected):
    before = fingerprint(path)
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 << 20), b''):
            h.update(block)
    require(fingerprint(path) == before, 'part_file_changed_while_hashing')
    require(expected == {'bytes': before['bytes'], 'sha256': h.hexdigest()},
            'part_input_hash_drift')
    return before


def save_exclusive(path, value):
    raw = json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode()
    with Path(path).open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    Path(path).chmod(0o400)
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    fingerprint(path)
    require(Path(path).stat().st_size <= 2**20, 'part_receipt_too_large')
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def completed_part(folder, binding, case, rank):
    folder = Path(folder)
    require(folder.is_dir() and not folder.is_symlink(), 'missing_part_directory')
    require({p.name for p in folder.iterdir()} == {'INTENT.json', 'progress.jsonl', 'SUCCESS.json', 'COMPLETE.json'},
            'incomplete_or_unexpected_part')
    for p in folder.iterdir():
        fingerprint(p)
    value = read_json(folder/'SUCCESS.json')
    complete = read_json(folder/'COMPLETE.json')
    require(complete == {'sha256': hashlib.sha256((folder/'SUCCESS.json').read_bytes()).hexdigest()},
            'part_completion_digest')
    require(set(value) == {'binding', 'case', 'rank', 'classification', 'input_fingerprints', 'payload_check', 'elapsed_seconds'},
            'part_receipt_schema')
    require(value['binding'] == binding and value['case'] == case
            and type(value['rank']) is int and value['rank'] == rank, 'part_identity_drift')
    require(value['classification'] == 'ONE_AUTHENTICATED_PAYLOAD_PART_NOT_FINAL_ACCEPTANCE', 'part_claim_scope')
    require(read_json(folder/'INTENT.json') == {'binding': binding, 'case': case, 'rank': rank},
            'part_intent_drift')
    require(set(value['input_fingerprints']) == set(payload_names(rank)), 'part_file_coverage')
    for fp in value['input_fingerprints'].values():
        require(set(fp) == {'dev', 'inode', 'bytes', 'mtime_ns', 'ctime_ns'}
                and all(type(n) is int and n >= 0 for n in fp.values()), 'part_fingerprint_schema')
    require(type(value['elapsed_seconds']) in (int, float) and math.isfinite(value['elapsed_seconds'])
            and value['elapsed_seconds'] >= 0, 'part_timing_invalid')
    result = value['payload_check']
    require(set(result) == {'classification', 'direct_roles_verified', 'parameters', 'master_groups', 'local_master_elements',
            'completed_steps', 'cumulative_valid_tokens', 'live_model_shards_independently_reconstructed',
            'direct_state_sha256', 'gpu_initialized'}, 'part_payload_schema')
    require(result['classification'] == 'ACTUAL_ZERO3_PAYLOAD_SIX_ROLE_OBSERVATION_CHECK_NOT_RESTART_PARITY'
            and result['direct_roles_verified'] == list(ROLES)
            and result['live_model_shards_independently_reconstructed'] is False
            and result['gpu_initialized'] is False, 'part_payload_scope')
    require(all(type(result[k]) is int and result[k] > 0 for k in ('parameters', 'master_groups', 'local_master_elements',
            'completed_steps', 'cumulative_valid_tokens')), 'part_payload_numeric_types')
    require(set(result['direct_state_sha256']) == set(ROLES), 'part_payload_role_coverage')
    return value


def complete_coverage(parts):
    addresses = [(v['case'], v['rank']) for v in parts]
    require(len(addresses) == len(PARTS) and set(addresses) == set(PARTS)
            and all(type(r) is int for _, r in addresses), 'incomplete_or_duplicate_payload_coverage')
