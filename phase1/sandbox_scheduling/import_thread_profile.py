"""CPU-only fixed-production import footprint. No agent/data/model execution.

Compares explicit host math-library cap3 with those three variables unset.
Login-node import measurements are not six-way production or historical cause.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

SOURCE='/research/d7/spc/yzyang4/resource-cache-qualification-20261011-v1/source/src'
CHILD=r'''
import os,sys,json,socket,time,resource,hashlib
from pathlib import Path
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:8])
def threads():
 return int(next(s for s in Path('/proc/self/status').read_text().splitlines() if s.startswith('Threads:')).split()[1])
def blocked(*a,**k):raise RuntimeError('network-disabled-import-only')
socket.socket.connect=blocked
socket.create_connection=blocked
import dotenv
dotenv.load_dotenv=lambda *a,**k:False
sys.path.insert(0,sys.argv[1])
before=threads(); start=time.monotonic();error=None
try:
 from dojo.config_dataclasses.run import RunConfig
 from dojo.main_run import _main
except Exception as e:error=type(e).__name__
samples=[]
for _ in range(3):samples.append(threads());time.sleep(.2)
print(json.dumps({'import_complete':error is None,'error_type':error,'before_threads':before,'after_threads':samples,
 'elapsed_seconds':time.monotonic()-start,'affinity_count':len(os.sched_getaffinity(0)),'nproc':list(resource.getrlimit(resource.RLIMIT_NPROC)),
 'numeric_library_caps':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
 'numpy_loaded':'numpy' in sys.modules,'torch_loaded':'torch' in sys.modules,'solver_instantiated':False,'network_disabled':True}))
'''


def main():
    base=Path(SOURCE); assert base.is_dir()
    out=[]
    for i,mode in enumerate(('capped','unset','unset','capped')):
        env=dict(os.environ,PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',WANDB_MODE='disabled',
            SUPERIMAGE_DIR='/research/d7/spc/yzyang4/aira-dojo/build/superimage',LOGGING_DIR='/research/d7/spc/yzyang4/resource-diag-stage-20261011.M5wKjU',
            MLE_BENCH_DATA_DIR='/nonexistent-import-only',CUDA_VISIBLE_DEVICES='')
        for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
            if mode=='capped':env[k]='3'
            else:env.pop(k,None)
        p=subprocess.Popen([sys.executable,'-B','-c',CHILD,SOURCE],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:stdout,stderr=p.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.communicate();out.append(dict(index=i,mode=mode,timeout=True));break
        lines=[json.loads(x) for x in stdout.splitlines() if x.startswith('{') and 'import_complete' in x]
        if p.returncode or len(lines)!=1:out.append(dict(index=i,mode=mode,returncode=p.returncode,unparsed=True));break
        out.append(dict(index=i,mode=mode,**lines[0]))
        if not lines[0]['import_complete']:break
    result=dict(source_commit='f7ccd79323112b10ccc82d8e9ec9d6cf089df607',
        source_sha256={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (base/'dojo/main_local_worker.py',base/'dojo/main_run.py')},
        cpu_only=True,gpu_jobs=0,model_or_candidate_execution=False,raw_output_exported=False,rows=out,
        boundary='Same-login-host imports only, not full agent lifetime, GPU kernels, exact historical failing environment, or causal explanation of archived EAGAIN.')
    print(json.dumps(result))


if __name__=='__main__':main()
