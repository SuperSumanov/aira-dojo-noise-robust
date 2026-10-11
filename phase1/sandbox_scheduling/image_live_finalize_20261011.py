"""Bounded postprocessing continuation of job17587, never submits any work.

One terminal-state readout after Slurm closure; no refit, rerun or outcome-based
adaptation. Writes at most once; stops on unknown accounting or evidence drift.
"""
import importlib.util,json,os,subprocess,sys,time,traceback
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v1')
JOB='17587';PIN='b44f6002b5da35d953a0ae1ead7b88d7776428cf7e775a26475fcce545837e78'
from lifecycle_pilot import read,write,sha

def run():
    assert sha(R/'plan.json')==PIN and read(R/'launch.json')['job']==JOB
    assert not (R/'readout-v1').exists()
    marker=R/'finalizer-claim.json';write(marker,dict(pid=os.getpid(),job=JOB,start=time.time(),max_wait_seconds=12000))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf');start=time.monotonic();account=None
    while time.monotonic()-start<12000:
        raw=subprocess.check_output(['sacct','-X','-j',JOB,'-n','-P','--format=JobIDRaw,State,ElapsedRaw,AllocTRES'],env=env,text=True,timeout=20)
        selected=[s.split('|') for s in raw.splitlines() if s.split('|')[0]==JOB]
        assert len(selected)<=1
        if selected:
            row=selected[0];state=row[1].split()[0]
            if state in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'):
                tres=dict(x.split('=',1) for x in row[3].split(',') if '=' in x)
                assert int(tres['gres/gpu'])==6
                account=dict(job=JOB,state=state,seconds=int(row[2]),gpus=6,gpu_seconds=int(row[2])*6)
                break
        time.sleep(30)
    if account is None:raise TimeoutError('bounded postprocessing wait expired')
    write(R/'accounting-v1.json',account)
    if not (R/'closed.json').exists():
        write(R/'finalizer-incomplete.json',dict(reason='controller closure missing',planned=32,accounting=account));return 2
    sys.path.insert(0,str(R))
    spec=importlib.util.spec_from_file_location('image_closed_readout',R/'image_live_readout_20261011.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.analyze(R,R/'readout-v1',account['gpu_seconds'])
    write(R/'finalizer-closed.json',dict(job=JOB,summary_sha256=sha(R/'readout-v1/summary.json'),
        scheduler_gpu_seconds=account['gpu_seconds'],no_gpu_or_api_or_new_job=True))
    return 0

if __name__=='__main__':
    os.umask(0o077)
    try:sys.exit(run())
    except Exception as e:
        path=R/'finalizer-failure.json'
        if not path.exists():write(path,dict(type=type(e).__name__,frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(e.__traceback__)]))
        raise
