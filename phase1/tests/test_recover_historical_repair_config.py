import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recover_historical_production_configs import RecoveryError
from recover_historical_repair_config import inspect


def fixture(tmp_path, *, duplicate=False, link=False, secret=False, bad_date=False):
    config = {'id': 'historical', 'task': {'name': 'test'}, 'meta_id': 'group',
              'metadata': {'launch_time': '2026-08-11T10:00:00', 'git_commit_id': 'a' * 40},
              'solver': {'algorithm': 'fixed'}, 'interpreter': {'type': 'test'}}
    if secret:
        config['sensitive'] = 'sk-' + 'x' * 32
    if bad_date:
        config['metadata']['launch_time'] = '2026-09-01T10:00:00'
    raw = json.dumps(config).encode()
    path = tmp_path / 'candidate.tar.gz'
    with tarfile.open(path, 'w:gz') as arc:
        for _ in range(2 if duplicate else 1):
            item = tarfile.TarInfo('batch/historical/dojo_config.json'); item.size = len(raw)
            arc.addfile(item, io.BytesIO(raw))
        # Header can be counted without parsing payload. Non-JSON by design.
        item = tarfile.TarInfo('batch/historical/checkpoint/journal.jsonl'); item.size = 12
        arc.addfile(item, io.BytesIO(b'not-json!!!!'))
        if link:
            item = tarfile.TarInfo('batch/data'); item.type = tarfile.SYMTYPE; item.linkname = '/unsafe'
            arc.addfile(item)
    expected = {'historical__2026-08-11': {'task': 'test', 'original_hold': 'unchanged'}}
    return path, hashlib.sha256(path.read_bytes()).hexdigest(), expected, time.monotonic() + 20


def test_recovers_config_only(tmp_path):
    records, counts = inspect(*fixture(tmp_path))
    assert len(records) == 1 and records[0]['original_hold'] == 'unchanged'
    assert counts['matching_journal_headers'] == counts['config_payloads_read'] == 1


@pytest.mark.parametrize('case', ['duplicate', 'link', 'secret'])
def test_rejects_unsafe_candidate(tmp_path, case):
    with pytest.raises(RecoveryError):
        inspect(*fixture(tmp_path, **{case: True}))


def test_date_does_not_alias_missing_run(tmp_path):
    records, _ = inspect(*fixture(tmp_path, bad_date=True))
    assert records == []


def test_hash_drift(tmp_path):
    path, _, expected, deadline = fixture(tmp_path)
    with pytest.raises(RecoveryError, match='candidate_hash_drift'):
        inspect(path, '0' * 64, expected, deadline)
