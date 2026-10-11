"""One bounded postprocessing of the declared16-row screen; never submits work."""
import os,re,subprocess,sys,time,json,traceback
from pathlib import Path
from lifecycle_pilot import read,write,sha

R=Path('/research/d7/spc/yzyang4/scheduling-image-generation-deadline-20261011-v1')
PIN='d153e408fb88e7ac120fceadbab79528275943e356a639871abb7e9dcc5f86b7'

def run(job):
    assert re.fullmatch(r'\d+',job) and sha(R/'plan.json')==PIN
    assert read(R/'launch.json')['job']==job and read(R/'plan.json')['planned']==16
    write(R/'completion-claim.json',dict(job=job,pid=os.getpid(),plan_sha256=PIN,
        start=time.time(),max_wait_seconds=7200,postprocessor_sha256=sha(__file__)))
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf');start=time.monotonic()
    while time.monotonic()-start<7200:
        raw=subprocess.check_output(['sacct','-X','-j',job,'-n','-P',
            '--format=JobIDRaw,State,ElapsedRaw,AllocTRES'],env=env,text=True,timeout=20)
        rows=[s.split('|') for s in raw.splitlines() if s.split('|')[0]==job]
        assert len(rows)<=1
        if rows and rows[0][1].split()[0] in ('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'):
            row=rows[0];tres=dict(x.split('=',1) for x in row[3].split(',') if '=' in x)
            assert int(tres['gres/gpu'])==6
            cost=6*int(row[2]);assert 0<=cost<=3120*6
            write(R/'accounting-v1.json',dict(job=job,state=row[1],seconds=int(row[2]),gpus=6,gpu_seconds=cost))
            break
        time.sleep(30)
    else:raise TimeoutError('bounded postprocessing expired')
    if not (R/'closed.json').exists():
        write(R/'completion-incomplete.json',dict(job=job,planned=16,reason='controller closure missing',gpu_seconds=cost));return
    sys.path.insert(0,str(R))
    from image_deadline_readout_20261011 import analyze
    analyze(R,R/'readout-v1',cost)
    result=read(R/'readout-v1/summary.json')
    write(R/'completion-closed.json',dict(job=job,plan_sha256=PIN,
        summary_sha256=sha(R/'readout-v1/summary.json'),gpu_seconds=cost,
        screen_positive=result['screen_positive'],no_gpu_or_api_or_new_job=True))
    print(json.dumps(read(R/'completion-closed.json')))

if __name__=='__main__':
    os.umask(0o077)
    try:run(sys.argv[1])
    except Exception as e:
        if not (R/'completion-error.json').exists():
            write(R/'completion-error.json',dict(type=type(e).__name__,
                frames=[dict(file=Path(f.filename).name,line=f.lineno,function=f.name) for f in traceback.extract_tb(e.__traceback__)]))
        raise
