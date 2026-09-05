import hashlib
import io
import os
import tarfile
import pytest
from phase1.scripts.verify_private_cuda128_20260906 import verify_prefix,archive_expected


@pytest.fixture
def prefix(tmp_path):
    p=tmp_path/'prefix';p.mkdir();(p/'file').write_bytes(b'actual')
    (p/'file').chmod(0o444);p.chmod(0o555)
    yield p
    p.chmod(0o755)
    (p/'file').chmod(0o644)


@pytest.mark.skipif(os.name!='posix',reason='POSIX readonly modes')
def test_real_readonly_file_matches(prefix):
    row={'file':{'kind':'file','bytes':6,'sha256':hashlib.sha256(b'actual').hexdigest(),'mode':0o444}}
    assert verify_prefix(prefix,row)==row


@pytest.mark.skipif(os.name!='posix',reason='POSIX readonly modes')
def test_unlisted_file_rejected(prefix):
    with pytest.raises(ValueError,match='archive_prefix_mismatch'):verify_prefix(prefix,{})


@pytest.mark.skipif(os.name!='posix',reason='POSIX readonly modes')
def test_writable_file_rejected(prefix):
    (prefix/'file').chmod(0o644)
    with pytest.raises(ValueError,match='prefix_regular_readonly'):verify_prefix(prefix,{})


@pytest.mark.skipif(os.name!='posix',reason='POSIX readonly modes')
def test_external_link_rejected(prefix,tmp_path):
    prefix.chmod(0o755);(prefix/'outside').symlink_to(tmp_path);prefix.chmod(0o555)
    with pytest.raises(ValueError,match='prefix_link_escape'):verify_prefix(prefix,{})


def archive(tmp_path,component,content=b'library',link='libx.so.1'):
    path=tmp_path/(component+'-archive.tar.xz');top=component+'-archive'
    with tarfile.open(path,'w:xz') as t:
        for name in (top,top+'/lib'):
            m=tarfile.TarInfo(name);m.type=tarfile.DIRTYPE;t.addfile(m)
        for name,data,mode in [('LICENSE',component.encode(),0o644),('lib/libx.so.1',content,0o755)]:
            m=tarfile.TarInfo(top+'/'+name);m.size=len(data);m.mode=mode;t.addfile(m,io.BytesIO(data))
        m=tarfile.TarInfo(top+'/lib/libx.so');m.type=tarfile.SYMTYPE;m.linkname=link;t.addfile(m)
    return path


def test_independent_archive_mapping_and_component_licenses(tmp_path):
    actual=archive_expected({name:archive(tmp_path,name) for name in ('a','b')})
    assert actual['share/components/a/LICENSE']['sha256']==hashlib.sha256(b'a').hexdigest()
    assert actual['share/components/b/LICENSE']['sha256']==hashlib.sha256(b'b').hexdigest()
    assert actual['lib/libx.so.1']['mode']==0o555
    assert actual['lib/libx.so']=={'kind':'symlink','target':'libx.so.1'}
    assert actual['lib64']=={'kind':'symlink','target':'lib'}


def test_independent_archive_collision_rejected(tmp_path):
    with pytest.raises(ValueError,match='archive_destination_collision'):
        archive_expected({'a':archive(tmp_path,'a'), 'b':archive(tmp_path,'b',b'different')})


def test_independent_archive_escape_rejected(tmp_path):
    with pytest.raises(ValueError,match='archive_link'):
        archive_expected({'a':archive(tmp_path,'a',link='../../../escape')})
