"""Fixed scope, enum-only gateway diagnostic audit."""
import json, os, re, subprocess, sys, time
from pathlib import Path
import persistent_readout as p
p.ROOT=Path('/research/d7/spc/yzyang4/resource-kernel-protocol-20261011-v1')
p.PIN='dab97495194cf57248451b24c806113456a91dd5d6d5ddb62fafd20c924183ac';p.JOB='17556'
ALLOWED=re.compile(r'^(?:(?:incoming|outgoing)_(?:kernel_info_request|kernel_info_reply|status|execute_request|execute_reply|error|other|unknown|forwarded)|nudge_(?:enter|done|failed|cancelled|state_starting|state_busy|state_idle|state_dead|state_other))$')

def audit():
    root=p.ROOT;assert p.sha(root/'plan.json')==p.PIN
    plan=p.read(root/'plan.json');closed=p.read(root/'closed.json')
    assert plan['planned']==48 and plan['schedule']==[dict(round=r,slot=s) for r in range(8) for s in range(6)]
    assert all(p.sha(root/n)==h for n,h in plan['files'].items())
    rows=[]
    for row in plan['schedule']:
        r,s=row['round'],row['slot'];ep=root/f'block-{r}-worker-{s}';f=root/f'round-{r}-slot-{s}.json'
        terminal=p.read(f) if f.exists() else {};gateway=p.read(ep/'gateway-counts.json') if (ep/'gateway-counts.json').exists() else None
        if gateway is not None:assert all(ALLOWED.fullmatch(k) and type(v) is int and v>=0 for k,v in gateway.items())
        complete=p.read(ep/'complete.json') if (ep/'complete.json').exists() else {}
        ex=p.read(ep/'execution.json') if (ep/'execution.json').exists() else {}
        rows.append(dict(**row,attempted=(ep/'host-before.json').exists(),complete=complete.get('complete',False),
             error_type=complete.get('error_type'),execution=ex,calls=terminal.get('calls',[]),gateway_counts=gateway,
             resource_failure=terminal.get('resource_failure'),host_threads=terminal.get('snapshot',{}).get('self_threads'),
             host_fds=terminal.get('snapshot',{}).get('self_fd_count')))
    assert sum(r['attempted'] for r in rows)==closed['attempted'] and sum(r['complete'] for r in rows)==closed['complete']
    pressure=[json.loads(x) for x in (root/'pressure.jsonl').read_text().splitlines()]
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-j',p.JOB,'-X','-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    acc=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==p.JOB];assert len(acc)==1
    state,seconds,tres=acc[0][1:4];assert state not in ('PENDING','RUNNING','COMPLETING')
    assert int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1])==1
    assert int(seconds)<=1800
    summary=dict(job=p.JOB,plan_sha256=p.PIN,closed_sha256=p.sha(root/'closed.json'),planned=48,attempted=closed['attempted'],complete=closed['complete'],
        unstarted=48-closed['attempted'],gateway_files=sum(r['gateway_counts'] is not None for r in rows),
        gateway_forwarding_observed=sum(bool((r['gateway_counts'] or {}).get('incoming_forwarded')) for r in rows),
        scheduler_state=state,gpu_seconds=int(seconds),gpu_seconds_cap=1800,
        uid_threads_peak=max(x['uid_counts']['visible_threads'] for x in pressure),
        nproc_soft_values=sorted({x['limits']['RLIMIT_NPROC'][0] for x in pressure}),
        after_uid_counts=p.read(root/'controller-after.json')['uid_counts'],rows=rows,
        boundary='Instrumented gateway direct entry and48 fixed CPU kernels; localization only, not unchanged-production reproduction, performance, six-GPU capacity or quality.')
    p.write(root/'audit-v1.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'}))
    print(json.dumps(dict(failures=[x for x in rows if x['attempted'] and not x['complete']])))

if __name__=='__main__':
    if sys.argv[1]=='launch':p.launch()
    elif sys.argv[1]=='audit':audit()
    elif sys.argv[1]=='watch':
        end=time.monotonic()+1900;last=None
        while time.monotonic()<end:
            try:value=p.status()
            except (OSError,ValueError):time.sleep(.5);continue
            if value!=last:print(json.dumps(value),flush=True);last=value
            if value['closed']:break
            time.sleep(15)
