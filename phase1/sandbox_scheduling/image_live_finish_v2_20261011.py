"""Bounded one-shot completion of the submitted v2 effect batch, no new job."""
import json,os,re,subprocess,sys,time
from pathlib import Path
from lifecycle_pilot import read,write,sha

R=Path('/research/d7/spc/yzyang4/scheduling-image-live-2plus4-20261011-v2')

def run(job,pin):
    assert re.fullmatch(r'\d+',job) and re.fullmatch(r'[a-f0-9]{64}',pin)
    assert sha(R/'plan.json')==pin and read(R/'launch.json')['job']==job
    write(R/'completion-claim.json',dict(job=job,pid=os.getpid(),plan_sha256=pin,start=time.time(),max_wait_seconds=28800))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf');start=time.monotonic()
    while time.monotonic()-start<28800:
        raw=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','--format=JobIDRaw,State,ElapsedRaw,AllocTRES'],env=env,text=True,timeout=20)
        rows=[s.split('|') for s in raw.splitlines() if s.split('|')[0]==job];assert len(rows)<=1
        if rows and rows[0][1].split()[0] in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'):
            row=rows[0];tres=dict(x.split('=',1) for x in row[3].split(',') if '=' in x);assert int(tres['gres/gpu'])==6
            cost=6*int(row[2]);write(R/'accounting-v1.json',dict(job=job,state=row[1],seconds=int(row[2]),gpus=6,gpu_seconds=cost,combined_gpu_seconds=cost+2634))
            break
        time.sleep(30)
    else:raise TimeoutError('bounded completion expired')
    if not (R/'closed.json').exists():
        write(R/'completion-incomplete.json',dict(reason='missing controller closure',job=job));return
    sys.path.insert(0,str(R))
    from image_live_readout_20261011 import analyze
    analyze(R,R/'readout-v1',cost)
    # Independent check of the repaired physical CPU split, not only the controller assertion.
    from live_identity import cores
    checks=[]
    for block in range(4):
        for lane in range(4):
            ids=[8*block+2*lane+k for k in (0,1)]
            files=[R/f'episode-{i}/cpu-partition.json' for i in ids]
            if not all(p.exists() for p in files):checks.append(False);continue
            pair=[read(p) for p in files];worker=[cores(x['worker_topology']) for x in pair]
            checks.append(len(worker[0])==len(worker[1])==2 and not worker[0]&worker[1]
                and worker[0]|worker[1]==cores(pair[0]['parent_topology'])==cores(pair[1]['parent_topology']))
    summary=read(R/'readout-v1/summary.json')
    write(R/'completion-closed.json',dict(job=job,plan_sha256=pin,readout_sha256=sha(R/'readout-v1/summary.json'),
        cpu_pairs_checked=16,cpu_pairs_passed=sum(checks),scheduler_gpu_seconds=cost,combined_gpu_seconds=cost+2634,
        exploratory_go=summary['exploratory_go'] and all(checks),no_new_job=True))

if __name__=='__main__':
    os.umask(0o077)
    try:run(*sys.argv[1:])
    except Exception as e:
        if not (R/'completion-error.json').exists():write(R/'completion-error.json',dict(type=type(e).__name__))
        raise
