from pathlib import Path
import io
import tarfile
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


def source_fixture(tmp_path,monkeypatch):
    source=tmp_path/'flash_attn-2.8.3';source.mkdir()
    archive=tmp_path/'source.tar.gz'
    inputs={'setup.py':b'fixed setup','csrc/kernel.cu':b'fixed code','PKG-INFO':b'old metadata'}
    with tarfile.open(archive,'w:gz') as tar:
        for name,data in inputs.items():
            p=source/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(data)
            info=tarfile.TarInfo('flash_attn-2.8.3/'+name);info.size=len(data);tar.addfile(info,io.BytesIO(data))
    monkeypatch.setattr(m,'SDIST_SHA',m.sha(archive))
    return archive,source


def test_whole_source_before_and_after_build(tmp_path,monkeypatch):
    archive,source=source_fixture(tmp_path,monkeypatch)
    assert m.verify_source_contents(archive,source)['original_files_verified']==3
    (source/'PKG-INFO').write_bytes(b'generated metadata')
    (source/'build').mkdir();(source/'build/generated.o').write_bytes(b'new build object')
    r=m.verify_source_contents(archive,source,after_build=True)
    assert r['original_files_verified']==2 and r['packaging_metadata_excluded_after_build']==['PKG-INFO']


@pytest.mark.parametrize('change',['kernel','extra','metadata_before','archive'])
def test_source_drift_rejected(tmp_path,monkeypatch,change):
    archive,source=source_fixture(tmp_path,monkeypatch)
    if change=='kernel':(source/'csrc/kernel.cu').write_bytes(b'changed code')
    if change=='extra':(source/'extra.py').write_bytes(b'new code')
    if change=='metadata_before':(source/'PKG-INFO').write_bytes(b'changed metadata')
    if change=='archive':monkeypatch.setattr(m,'SDIST_SHA','0'*64)
    with pytest.raises(AssertionError):m.verify_source_contents(archive,source)
    if change=='kernel':
        with pytest.raises(AssertionError,match='extracted_source_drift'):m.verify_source_contents(archive,source,after_build=True)
