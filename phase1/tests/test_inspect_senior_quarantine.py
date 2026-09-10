import io
import json
import tarfile
import pytest
from phase1.scripts import inspect_senior_quarantine_20260911 as m


def test_config_whitelist():
    data = {'metadata': {'git_commit_id': 'a'*40, 'host': 'not_exported'},
            'solver': {'_target_': 'dojo.MCTS', 'num_steps': 16, 'prompt': 'not_exported'},
            'unrelated': {'accuracy': 'not_exported'}}
    row = m.config_projection(json.dumps(data).encode())
    assert row == {'credential_refused': False, 'recorded_git_commit_id': 'a'*40,
                   'solver_fields': {'_target_': 'dojo.MCTS', 'num_steps': 16}}


def test_credential_scan_before_json():
    assert m.config_projection(b'not json sk-' + b'x'*24) == {'credential_refused': True}


def test_duplicate_config_key_rejected():
    with pytest.raises(ValueError): m.config_projection(b'{"metadata":{},"metadata":{}}')


def make_tar(path, records):
    with tarfile.open(path, 'w:gz') as f:
        for name, blob in records:
            item = tarfile.TarInfo(name); item.size = len(blob); f.addfile(item, io.BytesIO(blob))


def test_only_config_member_opened(tmp_path):
    p = tmp_path / 'fixture.tar.gz'
    make_tar(p, [('r/dojo_config.json', b'{"metadata":{},"solver":{}}'),
                 ('r/env_variables.json', b'not-json'), ('r/checkpoint/journal.jsonl', b'not-json')])
    rows, dirs, opened, headers = m.inspect_archive(p)
    assert len(rows) == 1 and dirs == {'r'} and opened == {'dojo_config.json': 1}
    assert headers['env_variables.json'] == headers['journal.jsonl'] == 1


@pytest.mark.parametrize('names', [['../bad'], ['r/x', 'r/x']])
def test_unsafe_tar(tmp_path, names):
    p = tmp_path / 'fixture.tar.gz'; make_tar(p, [(n, b'') for n in names])
    with pytest.raises(ValueError): m.inspect_archive(p)
