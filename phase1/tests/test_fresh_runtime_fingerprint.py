import hashlib,os
import pytest
from phase1.fresh_runtime_fingerprint import accept,digest,identity

@pytest.fixture(autouse=True)
def simulated_uid_on_windows(monkeypatch,tmp_path):
    # Windows unit tests simulate UID lookup; real qualification runs on Linux.
    if not hasattr(os,'getuid'):
        monkeypatch.setattr(os,'getuid',lambda:tmp_path.stat().st_uid,raising=False)

@pytest.fixture
def sample(tmp_path):
    p=tmp_path/'image';p.write_bytes(b'self-authored-runtime-test\n');return p

def test_known_bytes(sample):
    out=digest(sample)
    assert out['sha256']==hashlib.sha256(sample.read_bytes()).hexdigest()
    assert accept(out,out['sha256'],identity(sample))['source_admission'] is False

@pytest.mark.parametrize('value',[0,-1,601,True,float('nan'),float('inf')])
def test_bad_time(sample,value):
    with pytest.raises(ValueError):digest(sample,limit_seconds=value)

def test_relative():
    with pytest.raises(ValueError):identity('relative')

def test_symlink(sample):
    p=sample.parent/'link'
    try:p.symlink_to(sample)
    except OSError:pytest.skip('symlink capability absent')
    with pytest.raises(ValueError):identity(p)

def test_hardlink(sample):
    p=sample.parent/'hardlink';os.link(sample,p)
    with pytest.raises(ValueError):identity(sample)

def test_empty(sample):
    sample.write_bytes(b'')
    with pytest.raises(ValueError):identity(sample)

def test_size_bound(sample,monkeypatch):
    monkeypatch.setattr('phase1.fresh_runtime_fingerprint.MAX_BYTES',1)
    with pytest.raises(ValueError):identity(sample)

def test_hash_mismatch(sample):
    out=digest(sample)
    with pytest.raises(ValueError):accept(out,'0'*64,identity(sample))

def test_file_changed(sample):
    out=digest(sample);sample.write_bytes(b'different')
    with pytest.raises(ValueError):accept(out,out['sha256'],identity(sample))

def test_deadline(sample):
    ticks=iter([0.,601.])
    with pytest.raises(TimeoutError):digest(sample,clock=lambda:next(ticks))

def test_wrong_owner(sample,monkeypatch):
    uid=sample.stat().st_uid
    monkeypatch.setattr(os,'getuid',lambda:uid+1)
    with pytest.raises(ValueError):identity(sample)
