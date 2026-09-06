from pathlib import Path
import pytest
from phase1.scripts import build_fa2_cpu_20260907 as m


def test_explicit_compiler_and_cuda_arch(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m,'sha',lambda path:m.HOST_SHA)
    calls=[];records=[]
    monkeypatch.setattr(m,'invoke',lambda *args:calls.append(args))
    monkeypatch.setattr(m,'record',lambda *args:records.append(args))
    m.compiler_check('cpu')
    command=calls[0][1];environment=calls[0][2]
    assert command[command.index('-ccbin')+1]=='/usr/bin/g++'
    assert command[command.index('-arch=sm_120')]=='-arch=sm_120'
    assert all(environment[k]=='/usr/bin/g++' for k in ('CC','CXX','NVCC_CCBIN'))
    assert environment['CUDA_VISIBLE_DEVICES']=='' and calls[0][3]==45
    assert records[0][1]['gpu_context_created'] is False


def test_compiler_hash_drift_stops_before_spawn(monkeypatch,tmp_path):
    monkeypatch.setattr(m,'ROOT',tmp_path)
    monkeypatch.setattr(m,'sha',lambda path:'0'*64)
    monkeypatch.setattr(m,'invoke',lambda *args:pytest.fail('must not execute compiler'))
    with pytest.raises(AssertionError,match='host_compiler_changed'):m.compiler_check('cpu')
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('tag',['../outside','cpu/child','job-other',''])
def test_unsafe_compiler_tag_rejected(tag):
    with pytest.raises(AssertionError):m.compiler_check(tag)


def test_new_attempt_preserves_old_build():
    assert m.ROOT.name=='flash-attn-build-20260907-r3'
    source=Path(m.__file__).read_text()
    assert 'CC=HOST_CXX, CXX=HOST_CXX, NVCC_CCBIN=HOST_CXX' in source
    assert "FLASH_ATTN_CUDA_ARCHS='120'" in source
    assert "'automatic_retries': 0" in source
