"""Artificial metadata only; no credentials, network, archives, or model loads."""
import io
import pytest
from phase1.scripts import sync_senior_0907_0909_20260911 as m


def inventory():
    return {'folders': [
        {'relative': '0907', 'folder_id': 'folder_0907_id', 'entries': [
            [f'file_0907_{i:02}', f'archive{i}.tar.gz', 'application/gzip'] for i in range(2)]},
        {'relative': '0909', 'folder_id': 'folder_0909_id', 'entries': [
            ['folder_mcts_id', 'mcts', 'application/vnd.google-apps.folder']]},
        {'relative': '0909/mcts', 'folder_id': 'folder_mcts_id', 'entries': [
            [f'file_0909_{i:02}', f'archive{i}.tar.gz', 'application/gzip'] for i in range(6)]}]}


def test_scope_preserves_nested_group():
    assert [x['relative'] for x in m.validate_inventory(inventory())] == ['0907', '0909/mcts']


@pytest.mark.parametrize('kind', ['traversal', 'newline', 'duplicate', 'id', 'parent', 'count', 'extra', 'secret', 'folder'])
def test_bad_inventory(kind):
    v = inventory(); row = v['folders'][0]['entries'][0]
    if kind == 'traversal': row[1] = '../a.tar.gz'
    elif kind == 'newline': row[1] = 'a\n.tar.gz'
    elif kind == 'duplicate': v['folders'][0]['entries'][1][1] = row[1]
    elif kind == 'id': v['folders'][2]['entries'][0][0] = row[0]
    elif kind == 'parent': v['folders'][1]['entries'][0][0] = 'wrong_folder_id'
    elif kind == 'count': v['folders'][2]['entries'].pop()
    elif kind == 'extra': v['folders'].append(v['folders'][0])
    elif kind == 'secret': row[1] = 'sk-' + 'x'*24 + '.tar.gz'
    elif kind == 'folder': row[2] = 'application/vnd.google-apps.folder'
    with pytest.raises(RuntimeError): m.validate_inventory(v)


def test_writer_limits_and_hash(monkeypatch):
    monkeypatch.setattr(m, 'FILE_CAP', 5); monkeypatch.setattr(m, 'TOTAL_CAP', 7)
    budget = {'bytes': 0}; stream = io.BytesIO(); w = m.BoundedWriter(stream, budget)
    assert w.write(b'abc') == 3
    with pytest.raises(RuntimeError): w.write(b'def')
    assert stream.getvalue() == b'abc' and budget['bytes'] == 3
    w2 = m.BoundedWriter(io.BytesIO(), budget); w2.write(b'abcd')
    with pytest.raises(RuntimeError): w2.write(b'e')
    assert budget['bytes'] == 7
