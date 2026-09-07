"""Content identity for one runtime artifact; does not attest past execution."""
import hashlib,os,stat,time
from pathlib import Path

MAX_BYTES=25*2**30

def identity(path):
    p=Path(path)
    if not p.is_absolute() or '..' in p.parts or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('noncanonical_or_symlink')
    s=p.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_uid!=os.getuid():
        raise ValueError('file_owner_or_link')
    if not 0<s.st_size<=MAX_BYTES:raise ValueError('size_limit')
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def digest(path,*,limit_seconds=600,clock=time.monotonic):
    if type(limit_seconds) not in (int,float) or not 0<limit_seconds<=600:
        raise ValueError('time_limit')
    before=identity(path);start=clock();h=hashlib.sha256();count=0
    with Path(path).open('rb') as f:
        st=os.fstat(f.fileno())
        if (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)!=before:
            raise ValueError('opened_file_changed')
        while True:
            if clock()-start>limit_seconds:raise TimeoutError('fingerprint_deadline')
            raw=f.read(2**20)
            if not raw:break
            count+=len(raw)
            if count>before[2]:raise ValueError('file_grew')
            h.update(raw)
    if identity(path)!=before or count!=before[2]:raise ValueError('file_changed')
    return {'sha256':h.hexdigest(),'bytes':count,'identity':list(before)}

def accept(first,second_sha,after_identity):
    if (type(first) is not dict or set(first)!={'sha256','bytes','identity'} or
        type(first['sha256']) is not str or len(first['sha256'])!=64 or
        any(c not in '0123456789abcdef' for c in first['sha256'])):raise ValueError('invalid_first_digest')
    if first['sha256']!=second_sha or list(after_identity)!=first['identity']:
        raise ValueError('independent_hash_or_identity_changed')
    if first['bytes']!=first['identity'][2]:raise ValueError('byte_count')
    return {'classification':'CURRENT_RUNTIME_CONTENT_IDENTITY_NOT_HISTORICAL_ATTESTATION',
        'sha256':first['sha256'],'bytes':first['bytes'],'two_hash_implementations_equal':True,
        'historical_execution_attested':False,'candidate_programs_executed':0,'source_admission':False}
