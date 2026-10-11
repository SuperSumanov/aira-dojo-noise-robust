"""CPU-only Linux integration checks, never change the invoking process limits.

Each fresh child lowers only its own soft NPROC, restores it in finally, and
exits. No GPU, model, task data, command line or environment values are read.
This validates diagnostics under an injected limit, not a historical cause.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


CHILD = r'''
import json,os,resource,threading
import owned_process_pressure as p
assert os.getuid()!=0, 'Root is exempt; do not claim this verifies enforcement.'
original=resource.getrlimit(resource.RLIMIT_NPROC)
def one_thread():
    value=[]
    t=threading.Thread(target=lambda:value.append(True));t.start();t.join(2)
    assert value==[True] and not t.is_alive()
one_thread()
before=p.snapshot(os.getpid())
try:
    resource.setrlimit(resource.RLIMIT_NPROC,(1,original[1]))
    limited=p.snapshot(os.getpid())
    failure=None
    try:one_thread()
    except RuntimeError as exc:
        assert str(exc)=="can't start new thread"
        failure=type(exc).__name__
finally:
    resource.setrlimit(resource.RLIMIT_NPROC,original)
one_thread()
after=p.snapshot(os.getpid())
assert failure=='RuntimeError'
assert all(x['root_identity_stable'] for x in (before,limited,after))
assert all(len(x['owned_descendants'])==1 for x in (before,limited,after))
observed=[x['owned_descendants'][0]['limits']['RLIMIT_NPROC'] for x in (before,limited,after)]
assert observed[1][0]==1 and observed[0]==observed[2]
assert original==resource.getrlimit(resource.RLIMIT_NPROC)
print(json.dumps(dict(before=before,limited=limited,after=after,error_type=failure,
                     baseline_thread=True,restored_thread=True,limits_restored=True)))
'''


def run():
    import resource
    original = resource.getrlimit(resource.RLIMIT_NPROC)
    rows=[]
    for index in range(3):
        result=subprocess.run([sys.executable,'-B','-c',CHILD],capture_output=True,
                              text=True,timeout=15,check=True,
                              cwd=os.path.dirname(os.path.abspath(__file__)))
        rows.append(dict(index=index,**json.loads(result.stdout)))
    assert resource.getrlimit(resource.RLIMIT_NPROC)==original
    return dict(planned=3,complete=len(rows),rows=rows,parent_limits_unchanged=True,
                gpu_seconds=0,boundary='Injected child-only NPROC limit. Does not establish the cause of historical OpenBLAS EAGAIN or production capacity.')


class Tests(unittest.TestCase):
    @unittest.skipUnless(sys.platform=='linux' and os.getuid()!=0,'Needs Linux non-root UID')
    def test_three_child_only_limit_failures_and_restorations(self):
        self.assertEqual(run()['complete'],3)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='receipt':
        import hashlib
        result=run()
        result['source_sha256']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
            for n in ('test_owned_pressure_live.py','owned_process_pressure.py','resource_pressure.py')}
        target=Path(sys.argv[2])
        with target.open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
        print(json.dumps(dict(planned=result['planned'],complete=result['complete'],
            parent_limits_unchanged=result['parent_limits_unchanged'],gpu_seconds=0,
            artifact=str(target),sha256=hashlib.sha256(target.read_bytes()).hexdigest())))
    else:
        unittest.main()
