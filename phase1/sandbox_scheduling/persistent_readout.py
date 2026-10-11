"""Independent structural readout. No arbitrary text, labels or predictions."""
import csv, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/resource-persistent-hosts-20261011-v1')
PIN='8435e7595bc316fc4ee08b8e48a710adc5b5bcc5529dcad1bb88336f607d62cb'
JOB='17555'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    with p.open('x') as f:json.dump(v,f,indent=2,sort_keys=True,allow_nan=False)

def launch():
    assert sha(ROOT/'plan.json')==PIN
    write(ROOT/'launch.json',dict(job=JOB,plan_sha256=PIN,recorded_utc_seconds=time.time()))
    print(json.dumps(dict(job=JOB,launch_recorded=True)))

def status():
    out=dict(job=JOB,started=len(list(ROOT.glob('block-*-worker-*/host-before.json'))),
             terminal=len(list(ROOT.glob('block-*-worker-*/complete.json'))),
             complete_rounds=len(list(ROOT.glob('round-*-after.json'))),closed=(ROOT/'closed.json').exists())
    if out['closed']:out['closed_summary']=read(ROOT/'closed.json')
    return out

def audit():
    assert sha(ROOT/'plan.json')==PIN
    p=read(ROOT/'plan.json');closed=read(ROOT/'closed.json')
    assert p['planned']==192 and p['width']==6 and p['rounds']==32 and p['gpus']==1
    assert all(sha(ROOT/n)==h for n,h in p['files'].items())
    assert p['schedule']==[dict(round=r,slot=s) for r in range(32) for s in range(6)]
    rows=[];hosts=[];global_rows=[]
    for s in range(6):
        base=read(ROOT/f'host-{s}-baseline.json');observed=[]
        for r in range(32):
            ep=ROOT/f'block-{r}-worker-{s}';final=ROOT/f'round-{r}-slot-{s}.json'
            c=read(ep/'complete.json') if (ep/'complete.json').exists() else {}
            item=read(final) if final.exists() else {};snap=item.get('snapshot',{})
            k=read(ep/'kernel.json') if (ep/'kernel.json').exists() else {}
            ex=read(ep/'execution.json') if (ep/'execution.json').exists() else {}
            if snap:assert snap['pid']==base['pid']
            ok=bool(c.get('complete') and item.get('returncode')==0 and k.get('check') and ex.get('exit_code')==0 and not ex.get('timed_out',True))
            row=dict(round=r,slot=s,job=JOB,source_commit=p['source_commit'],plan_sha256=PIN,source_seed=p['source_seed'],
                attempted=(ep/'host-before.json').exists(),terminal=bool(c),complete=ok,error_type=c.get('error_type'),
                host_pid=snap.get('pid'),host_threads=snap.get('self_threads'),host_fds=snap.get('self_fd_count'),
                kernel_seconds=ex.get('seconds'),uid_threads=snap.get('uid_counts',{}).get('visible_threads'))
            rows.append(row)
            if snap:observed.append(row)
        hosts.append(dict(slot=s,pid=base['pid'],baseline_threads=base['self_threads'],baseline_fds=base['self_fd_count'],
             observed_rounds=len(observed),threads=[x['host_threads'] for x in observed],fds=[x['host_fds'] for x in observed]))
    assert len({h['pid'] for h in hosts})==6
    for r in range(32):
        f=ROOT/f'round-{r}-after.json'
        if f.exists():global_rows.append(dict(round=r,**read(f)['uid_counts']))
    assert sum(x['attempted'] for x in rows)==closed['attempted']
    assert sum(x['complete'] for x in rows)==closed['complete']
    flags={x:0 for x in ('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')}
    for f in ROOT.glob('host-*.private.log'):
        raw=f.read_text(errors='replace').lower()
        for x in flags:flags[x]+=raw.count(x)
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    out=subprocess.check_output(['sacct','-j',JOB,'-X','-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    acc=[x.split('|') for x in out.splitlines() if x.split('|')[0]==JOB];assert len(acc)==1
    state,seconds,tres=acc[0][1:4];assert state not in ('RUNNING','COMPLETING','PENDING')
    assert int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1])==1
    cost=int(seconds);assert cost<=p['gpu_seconds_cap']
    summary=dict(job=JOB,plan_sha256=PIN,closed_sha256=sha(ROOT/'closed.json'),planned=192,
         attempted=closed['attempted'],complete=closed['complete'],unstarted=192-closed['attempted'],
         complete_rounds=closed['complete_rounds'],scheduler_state=state,error_type=closed['error_type'],
         gpu_seconds=cost,gpu_seconds_cap=1800,hosts=hosts,after_round_uid_counts=global_rows,
         controller_after_uid=read(ROOT/'controller-after.json')['uid_counts'],resource_error_markers=flags,
         full_lifecycle_gate=closed['complete']==192 and closed['host_returncodes']==[0]*6 and state=='COMPLETED' and not any(flags.values()),
         limits=['CPU-only fixed arithmetic, no production DataLoader/model pressure','round31 group counts may include hosts already exiting','visible UID counts are lower bounds; no universal no-leak or historical-cause claim','Slurm process-cgroup cleanup must be checked independently'])
    write(ROOT/'audit-v1.json',summary)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(summary))

if __name__=='__main__':
    if sys.argv[1]=='launch':launch()
    elif sys.argv[1]=='audit':audit()
    elif sys.argv[1]=='watch':
        end=time.monotonic()+1900;last=None
        while time.monotonic()<end:
            try:value=status()
            except (OSError,ValueError):time.sleep(.5);continue
            if value!=last:print(json.dumps(value),flush=True);last=value
            if value['closed']:break
            time.sleep(15)
    else:raise ValueError('mode')
