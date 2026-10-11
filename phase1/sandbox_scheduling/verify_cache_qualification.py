"""Independent two-program qualification; no test labels or scores."""
import csv
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from verify_six_gpu_capacity import sha, read, output, topology


def verify(root,pin,job):
    assert sha(root/'plan.json')==pin
    p=read(root/'plan.json');c=read(root/'closed.json');launch=read(root/'launch.json')
    assert launch==dict(job=job,plan_sha256=pin)
    assert p['qualification'] and p['planned']==c['planned']==2 and p['gpus']==1 and p['gpu_seconds_cap']==1200
    assert [(r['index'],r['program'],r['width']) for r in p['schedule']]==[(0,0,1),(1,1,1)]
    manifest=all(sha(root/n)==h for n,h in p['files'].items());rows=[]
    returned={r['index']:r for r in c['rows']};assert len(returned)==len(c['rows'])
    for r in p['schedule']:
        ep=root/f"episode-{r['index']}";done=read(ep/'complete.json') if (ep/'complete.json').exists() else {}
        row=dict(**r,job=job,plan_sha256=pin,source_commit=p['source_commit'],source_seed=42,
            attempted=r['index'] in returned,complete=done.get('complete',False),
            error_type=done.get('error_type'),gpu_steps=None,execution_seconds=None,output_rows=None,output_sha256=None)
        if row['complete']:
            e=read(ep/'execution.json');t=read(ep/'gpu-training.json');ident=read(ep/'identity.json')
            assert e['exit_code']==returned[r['index']]['returncode']==0 and not e['timed_out']
            assert ident['job']==job and len(set(ident['gpu_uuids']))==1 and len(topology(ident['cpu_topology']))==4
            steps=t['host_step_intervals'];assert steps and len(steps)==t['steps']
            assert all(x['devices']==['cuda:0'] and x['gradient_parameters']>0 for x in steps)
            head,values=output(ep/'output.private.csv')
            with (Path(p['programs'][r['program']]['data'])/'test.csv').open(newline='') as f:
                reader=csv.reader(f);next(reader);ids=[x[0] for x in reader]
            assert len(set(ids))==len(ids)==len(values) and set(ids)==values.keys()
            row.update(gpu_steps=t['steps'],execution_seconds=e['seconds'],output_rows=len(values),output_sha256=sha(ep/'output.private.csv'))
            assert read(ep/'output-structure.json')['sha256']==row['output_sha256']
        rows.append(row)
    assert sum(x['complete'] for x in rows)==c['complete'] and sum(x['attempted'] for x in rows)==c['attempted']
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-j',job,'-X','-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    account=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==job];assert len(account)==1
    state,seconds,tres=account[0][1:4];assert state not in ('PENDING','RUNNING','COMPLETING')
    assert re.search(r'(?:^|,)gres/gpu=1(?:,|$)',tres) and int(seconds)<=1200
    result=dict(job=job,plan_sha256=pin,closed_sha256=sha(root/'closed.json'),manifest_ok=manifest,
        planned=2,attempted=c['attempted'],complete=c['complete'],unstarted=2-c['attempted'],
        scheduler_state=state,gpu_seconds=int(seconds),gpu_seconds_cap=1200,rows=rows,
        gate=bool(manifest and c['complete']==2 and state=='COMPLETED'),
        boundary='Entry/cache qualification only; not six-way capacity, speedup, quality, or historical EAGAIN root cause.')
    return rows,result


if __name__=='__main__':
    root=Path(sys.argv[1]);pin=sys.argv[2];job=sys.argv[3]
    assert root==Path('/research/d7/spc/yzyang4/resource-cache-qualification-20261011-v1')
    assert re.fullmatch('[a-f0-9]{64}',pin) and job.isdigit()
    rows,result=verify(root,pin,job)
    with (root/'qualification-audit.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (root/'qualification-audit.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result))
