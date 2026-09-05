from types import SimpleNamespace

import pytest

from phase1.scripts import inspect_gpu28_cuda_toolchains_20260906 as mod


def test_shallow_inventory_never_recurses_unrelated_tree(tmp_path, monkeypatch):
    (tmp_path/'unrelated').mkdir()
    (tmp_path/'unrelated'/'cuda-12.8').mkdir()
    (tmp_path/'cuda-12.8').mkdir()
    monkeypatch.setattr(mod,'ROOTS',(tmp_path,))
    rows = mod.discover_toolchains()
    assert len(rows)==1 and rows[0]['prefix']==str(tmp_path/'cuda-12.8')
    assert rows[0]['nvcc_release'] is None and not any(rows[0]['files_present'].values())


def test_version_parser_retains_complete_and_incomplete_prefixes(tmp_path, monkeypatch):
    for name in ('cuda-12.8','cuda-11.8'):
        (tmp_path/name/'bin').mkdir(parents=True)
        (tmp_path/name/'bin/nvcc').write_bytes(b'fixture-not-executable')
    monkeypatch.setattr(mod,'ROOTS',(tmp_path,))
    def fake(argv, **kwargs):
        version = b'12.8' if '12.8' in argv[0] else b'11.8'
        assert argv[1:] == ['--version'] and 0<kwargs['timeout']<=10
        return SimpleNamespace(returncode=0,stdout=b'Cuda compilation tools, release '+version+b', V0')
    monkeypatch.setattr(mod.subprocess,'run',fake)
    rows = mod.discover_toolchains()
    assert [r['nvcc_release'] for r in rows]==['11.8','12.8']
    assert all(r['files_present']['bin/nvcc'] and not r['files_present']['include/cuda.h'] for r in rows)


def test_unknown_compiler_output_is_not_echoed(tmp_path, monkeypatch):
    (tmp_path/'cuda'/'bin').mkdir(parents=True)
    (tmp_path/'cuda'/'bin/nvcc').write_bytes(b'fixture')
    monkeypatch.setattr(mod,'ROOTS',(tmp_path,))
    monkeypatch.setattr(mod.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=1,stdout=b'PRIVATE ERROR CONTENT'))
    rows=mod.discover_toolchains()
    assert rows[0]['nvcc_release'] is None and rows[0]['nvcc_returncode']==1
    assert 'PRIVATE ERROR' not in str(rows)


def test_too_many_prefixes_stop_before_executing(tmp_path, monkeypatch):
    for n in range(21): (tmp_path/f'cuda-{n}').mkdir()
    monkeypatch.setattr(mod,'ROOTS',(tmp_path,))
    with pytest.raises(AssertionError): mod.discover_toolchains()
