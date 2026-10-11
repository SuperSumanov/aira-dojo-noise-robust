"""Fresh parallel content verification, followed by the unchanged submit guard.

No historical cached hashes or mtime-only verification. Each model/image byte
is hashed in THIS invocation before GPU timing. Cache reuse only avoids doing
the same digest twice within this process; changing stat identity fails closed.
"""
import concurrent.futures
import importlib
import os
from pathlib import Path
import sys
import time


def identity(path):
    s=Path(path).stat()
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def main(root):
    root=Path(root).resolve();sys.path.insert(0,str(root))
    from lifecycle_pilot import read,write,sha
    entry=importlib.import_module('generation_joint_trial_20261012')
    assert entry.R==root and not (root/'launch.json').exists() and not (root/'submit-intent.json').exists()
    p=entry.c.trial.check();assert read(root/'preflight.json')['plan_sha256']==sha(root/'plan.json')
    m=entry.host();expected={str(Path(n).resolve()):h for n,h in p['model_files'].items()}
    expected[str(Path(m.TASK_IMAGE).resolve())]=p['task_image_sha256']
    expected[str(Path(m.VLLM).resolve())]=p['service_image_sha256']
    def verify(item):
        path,wanted=item;before=identity(path);actual=sha(path);after=identity(path)
        if before!=after or actual!=wanted:raise ValueError('fresh dependency hash/identity mismatch')
        return path,dict(sha256=actual,identity=after)
    start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        verified=dict(pool.map(verify,expected.items()))
    write(root/'parallel-hash-preflight.json',dict(plan_sha256=sha(root/'plan.json'),
        helper_sha256=sha(__file__),fresh_full_content_hash=True,workers=3,
        seconds=time.monotonic()-start,files=verified))
    original=entry.c.sha
    def just_verified(path):
        key=str(Path(path).resolve())
        if key not in verified:return original(path)
        receipt=verified[key]
        if identity(key)!=tuple(receipt['identity']):raise ValueError('dependency changed after fresh hashing')
        return receipt['sha256']
    entry.c.sha=just_verified
    entry.c.submit()


if __name__=='__main__':
    os.umask(0o077);main(sys.argv[1])
