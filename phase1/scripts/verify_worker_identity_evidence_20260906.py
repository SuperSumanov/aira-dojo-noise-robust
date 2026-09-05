"""Independent reparse of two fixed worker identities; emit aggregate evidence."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tarfile

ROOT = Path('/research/d7/spc/yzyang4')
SECRET = re.compile(rb'(?i)(?:sk-[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9_.-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, 'duplicate_json_key'
        result[key] = value
    return result


def locked(path, expected):
    raw = path.read_bytes()
    assert sha(raw) == expected
    return json.loads(raw, object_pairs_hook=unique)


def verify():
    os.umask(0o077)
    ledger = locked(ROOT/'historical-source-ledger-faf04cc-20260905/source_ledger.private.json',
                    '8e48b4c6598cf8efe205fc6cba5cdd27d14621eb13fad42a7fd4180953da00d1')
    lineage = locked(ROOT/'historical-pool-lineage-e7244fb-20260906-A/pool_lineage.private.json',
                     'fe05dddcd4fe8a3f2208652ce51c9b06df9b9b8f57a5fa655d2029caddcf9981')
    conflicts = [(m, t) for m in lineage['manifests'] for t in m['tasks']
                 if t['step_matches_recorded_config'] is False]
    assert len(conflicts) == 1
    manifest, task = conflicts[0]
    origins = ledger[task['run_id']]['origins']
    assert len({o['recorded_slurm_id'] for o in origins}) == 1
    config_step = origins[0]['recorded_slurm_id']
    assert lineage['closure'][task['run_id']]['old_hold_closure_blocks_train']
    inventory_path = ROOT/'senior-true-batch-identity-support/a466888-v3/producer_1/archive_manifest.jsonl'
    inventory_raw = inventory_path.read_bytes()
    assert sha(inventory_raw) == '72b74df7387254afc5ca3ec5d79029e74ae8371faa6216742e63be899419e8fd'
    candidates = {r['relative_path'] for line in inventory_raw.splitlines()
                  if (r := json.loads(line))['status'] == 'ok' and r['sha256'] == manifest['archive_sha256']}
    assert len(candidates) == 1
    relative = PurePosixPath(next(iter(candidates)))
    assert not relative.is_absolute() and '..' not in relative.parts
    archive = ROOT/'external/senior_data/mle'/str(relative)
    assert not archive.is_symlink() and sha(archive.read_bytes()) == manifest['archive_sha256']
    base = PurePosixPath(manifest['identity']['pool_dir']).parent.parent.parent
    expected = {str(PurePosixPath(a['identity_path']).relative_to(base)): a for a in task['attempts']}
    assert len(expected) == len(task['attempts']) == 2
    producer_raw = (ROOT/'historical-worker-identity-triage-20260906.json').read_bytes()
    assert not SECRET.search(producer_raw)
    producer = json.loads(producer_raw, object_pairs_hook=unique)
    checks = []
    with tarfile.open(archive, 'r:*') as tar:
        selected = [m for m in tar.getmembers() if m.name in expected]
        assert len(selected) == len({m.name for m in selected}) == 2
        for member in selected:
            assert member.isfile() and 0 < member.size < 8192
            raw = tar.extractfile(member).read()
            assert len(raw) == member.size and not SECRET.search(raw)
            identity = json.loads(raw, object_pairs_hook=unique)
            assert set(identity) == {'run_id','attempt','allocation_id','step_id','full_step_id','pid','started_at'}
            attempt = expected[member.name]
            assert identity['run_id'] == task['config_id'] and identity['attempt'] == attempt['attempt']
            full_step = str(identity['allocation_id']) + '.' + str(identity['step_id'])
            assert identity['full_step_id'] == full_step
            record = dict(attempt=identity['attempt'], identity_started_at=identity['started_at'],
                          recorded_attempt_started_at=attempt['started_at'],
                          identity_matches_config_step=full_step == config_step,
                          identity_matches_manifest_attempt_step=full_step == attempt['step_id'],
                          manifest_attempt_step_empty=attempt['step_id'] == '', identity_sha256=sha(raw))
            assert record in producer['identities']
            checks.append(record)
    assert sha(archive.read_bytes()) == manifest['archive_sha256']
    checks.sort(key=lambda r: r['attempt'])
    assert checks[-1]['identity_matches_config_step'] and checks[-1]['manifest_attempt_step_empty']
    assert checks[0]['identity_matches_manifest_attempt_step']
    result = dict(status='INDEPENDENT_ARCHIVED_WORKER_IDENTITY_REPARSE_VERIFIED',
                  identity_files=len(checks), archive_sha256=manifest['archive_sha256'],
                  producer_receipt_sha256=sha(producer_raw), verifier_source_sha256=sha(Path(__file__).read_bytes()),
                  checks=checks, original_hold_kept=True, original_lineage_rewritten=False,
                  controller_exception_count=1, journal_log_env_payload_reads=0,
                  interpretation='latest worker identity supports config; latest controller step field is empty; exact cause not established',
                  runtime_environment_attested=False, training_admitted=False)
    out = ROOT/'historical-worker-identity-independent-20260906.json'
    with out.open('x') as handle:
        json.dump(result, handle, sort_keys=True)
        handle.write('\n')
    out.chmod(0o400)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    verify()
