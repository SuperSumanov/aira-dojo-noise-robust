import errno,json,os
from pathlib import Path
import pytest
from phase1 import pivot_checkpoint_space as m


pytestmark=pytest.mark.skipif(not hasattr(os,'posix_fallocate'),reason='POSIX allocation probe requires Linux')


def test_actual_own_allocation_and_release(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'SIZE',1024*1024)
    untouched=tmp_path/'user-file';untouched.write_bytes(b'user-owned')
    r=m.probe(tmp_path)
    assert r['passed'] and r['allocated_bytes']>=1024*1024 and r['other_files_removed']==0
    assert not (tmp_path/'own-checkpoint-space-probe.bin').exists()
    assert untouched.read_bytes()==b'user-owned'
    assert json.loads((tmp_path/'space-probe-released.json').read_text())['own_inode_removed'] is True
    with pytest.raises(ValueError,match='already_attempted'):m.probe(tmp_path)


def test_refused_quota_stops_and_preserves_evidence(tmp_path,monkeypatch):
    def refused(*args):raise OSError(errno.EDQUOT,'simulated quota')
    monkeypatch.setattr(os,'posix_fallocate',refused)
    with pytest.raises(ValueError,match='capacity_probe_failed'):m.probe(tmp_path)
    r=json.loads((tmp_path/'space-probe.json').read_text())
    assert r['passed'] is False and r['error']['errno']==errno.EDQUOT
    assert not (tmp_path/'own-checkpoint-space-probe.bin').exists()


def test_sparse_truncate_cannot_pass(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'SIZE',1024*1024)
    monkeypatch.setattr(os,'posix_fallocate',lambda fd,offset,size:os.ftruncate(fd,size))
    with pytest.raises(ValueError,match='capacity_probe_failed'):m.probe(tmp_path)


def test_symlink_and_existing_files_are_not_touched(tmp_path):
    target=tmp_path/'real';target.mkdir();link=tmp_path/'alias';link.symlink_to(target,target_is_directory=True)
    with pytest.raises(ValueError,match='space_probe_root'):m.probe(link)
    file=target/'own-checkpoint-space-probe.bin';file.write_bytes(b'old')
    with pytest.raises(ValueError,match='already_attempted'):m.probe(target)
    assert file.read_bytes()==b'old'


def test_hardlink_injected_never_deleted(tmp_path,monkeypatch):
    original=os.posix_fallocate;monkeypatch.setattr(m,'SIZE',1024*1024)
    def link_after_allocate(fd,offset,size):
        original(fd,offset,size)
        os.link(tmp_path/'own-checkpoint-space-probe.bin',tmp_path/'unexpected-link')
    monkeypatch.setattr(os,'posix_fallocate',link_after_allocate)
    with pytest.raises(ValueError,match='inode_changed'):m.probe(tmp_path)
    assert (tmp_path/'own-checkpoint-space-probe.bin').exists()
    assert (tmp_path/'unexpected-link').exists()
