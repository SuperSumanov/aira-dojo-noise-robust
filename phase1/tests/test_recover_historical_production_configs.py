import hashlib
import io
import json
import tarfile
import time

import pytest

from phase1 import recover_historical_production_configs as recovery


def fixture():
    config = dict(id='historical-run', meta_id='runner-recipe',
                  metadata=dict(launch_time='2026-08-01 12:00:00', git_commit_id='a'*40, slurm_id='123'),
                  task=dict(name='synthetic-task'), solver=dict(time_limit_secs=10), interpreter=dict(name='test'))
    expected = {'historical-run__2026-08-01': dict(task='synthetic-task', original_hold=False)}
    return config, expected


def test_literal_tracking_is_recovered_not_imputed():
    config, expected = fixture()
    row = recovery.config_record(json.dumps(config).encode(), 'b'*64,
                                 'batch/historical-run/dojo_config.json', expected)
    assert row['recorded_runner_git_commit'] == 'a'*40
    assert row['recorded_meta_id'] == 'runner-recipe'
    config['meta_id'] = ''
    config['metadata']['git_commit_id'] = 'unknown'
    row = recovery.config_record(json.dumps(config).encode(), 'b'*64,
                                 'batch/historical-run/dojo_config.json', expected)
    assert row['recorded_runner_git_commit'] is None and row['recorded_meta_id'] is None


def test_different_launch_date_is_not_matched_by_directory_name():
    config, expected = fixture()
    config['metadata']['launch_time'] = '2026-08-02 12:00:00'
    assert recovery.config_record(json.dumps(config).encode(), 'b'*64,
                                  'batch/historical-run/dojo_config.json', expected) is None


@pytest.mark.parametrize('fault', ['credential', 'duplicate_key', 'directory', 'task'])
def test_bad_config_refused_before_record(fault):
    config, expected = fixture()
    member = 'batch/historical-run/dojo_config.json'
    if fault == 'credential':
        config['credential_fixture'] = 'sk-' + 'x'*24
    elif fault == 'directory':
        member = 'batch/different/dojo_config.json'
    elif fault == 'task':
        config['task']['name'] = 'other'
    raw = json.dumps(config).encode()
    if fault == 'duplicate_key':
        raw = raw[:-1] + b',"id":"historical-run"}'
    with pytest.raises(recovery.RecoveryError):
        recovery.config_record(raw, 'b'*64, member, expected)


@pytest.mark.parametrize('duplicate', [False, True])
def test_archive_only_opens_known_config_members(tmp_path, monkeypatch, duplicate):
    config, expected = fixture()
    path = tmp_path / 'archive.tar.gz'
    with tarfile.open(path, 'w:gz') as archive:
        items = [('batch/historical-run/dojo_config.json', json.dumps(config).encode()),
                 ('batch/historical-run/checkpoint/journal.jsonl', b'DO_NOT_PARSE_OUTCOMES'),
                 ('batch/historical-run/env_variables.json', b'DO_NOT_PARSE_ENV')]
        if duplicate:
            items.append(items[0])
        for name, content in items:
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    opened = []
    original = tarfile.TarFile.extractfile
    def record_open(self, member):
        assert member.name.endswith('/dojo_config.json')
        opened.append(member.name)
        return original(self, member)
    monkeypatch.setattr(tarfile.TarFile, 'extractfile', record_open)
    monkeypatch.setattr(recovery, 'SOURCE', tmp_path)
    output = tmp_path / 'results'
    output.mkdir()
    row = dict(status='ok', relative_path=path.name, size=path.stat().st_size,
               sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    result = recovery.scan_one(0, row, expected, {'historical-run'}, output, time.monotonic()+60)
    assert len(opened) == 1
    assert result['status'] == ('FAILED_CLOSED' if duplicate else 'CONFIG_RECORDS_RECOVERED')
    if duplicate:
        assert result['reason'] == 'duplicate_or_nonfile_config_member'
    else:
        assert len(result['records']) == 1


def test_old_error_archive_not_opened(tmp_path):
    result = recovery.scan_one(0, {'status': 'error'}, {}, set(), tmp_path, time.monotonic()+60)
    assert result['status'] == 'OLD_ARCHIVE_ERROR_NOT_OPENED'
    assert result['config_members_read'] == 0
