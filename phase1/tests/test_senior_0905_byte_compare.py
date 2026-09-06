import hashlib,time
import pytest
from phase1.scripts import verify_senior_0905_existing_bytes_20260907 as m


def test_hash_writer_handles_split_prefix_without_storing_body():
    budget=[0];w=m.HashOnlyWriter(budget,time.monotonic()+10)
    for b in [b'\x1f',b'\x8b',b'\x08',b'opaque']:assert w.write(b)==len(b)
    assert w.prefix==b'\x1f\x8b\x08' and w.n==9 and budget[0]==9
    assert w.h.hexdigest()==hashlib.sha256(b'\x1f\x8b\x08opaque').hexdigest()
    assert not hasattr(w,'f')


@pytest.mark.parametrize('case',['file','total','time'])
def test_stream_limits_fail_before_accepting_bytes(monkeypatch,case):
    w=m.HashOnlyWriter([0],time.monotonic()+10)
    if case=='file':monkeypatch.setattr(m,'FILE_CAP',2)
    elif case=='total':w.budget[0]=m.TOTAL_CAP-2
    else:w.deadline=time.monotonic()-1
    with pytest.raises(RuntimeError,match='budget'):w.write(b'abc')
    assert w.n==0


@pytest.mark.parametrize('method,url,ok',[
    ('GET','https://drive.google.com/uc?id=x',True),('GET','https://drive.usercontent.google.com/download',True),
    ('GET','https://a.googleusercontent.com/download',True),('POST','https://drive.google.com/uc',False),
    ('GET','http://drive.google.com/uc',False),('GET','https://evilgoogle.com/uc',False),
    ('GET','https://drive.google.com.evil.test/uc',False)])
def test_network_scope(method,url,ok):assert m.allowed_request(method,url) is ok
