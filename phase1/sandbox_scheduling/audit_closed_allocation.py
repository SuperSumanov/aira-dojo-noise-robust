"""Closed 16370 allocation/timing evidence only, without candidate or quality fields."""
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess

R=Path('/research/d7/spc/yzyang4/implementation-reset-20261005-v2')
PLAN_SHA='c1aba6663872c01c656f4da45667f5d0dc60e589fec6fe5f87fc00dcbc9a2d6a'
COST_SHA='724018a317d8b540e6893c5abedf9ccd0d7908682349517b45c3e1e5147d1184'
SECRET=re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def main():
    os.umask(0o077)
    hashes={}
    def read(name,pin=None):
        raw=(R/name).read_bytes();h=hashlib.sha256(raw).hexdigest()
        if pin and h!=pin:raise ValueError('source drift')
        if SECRET.search(raw):raise ValueError('credential-shaped source withheld')
        hashes[name]=h
        return json.loads(raw)
    plan=read('plan.json',PLAN_SHA)
    # Already released public timing artifact. No action/code/score fields accessed.
    times={row['index']:{k:row[k] for k in ('arm','task','returned_generation_seconds')}
           for row in read('readout-v1/mechanism-cost.json',COST_SHA)['rows']}
    service=read('service-native.json')
    if service['job']!='16370' or len(service['gpu_uuids'])!=2:raise ValueError('service mismatch')
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-j','16370','-n','-P',
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=15)
    accounting={}
    for line in raw.splitlines():
        fields=line.split('|')
        accounting[fields[0]]=dict(state=fields[1],elapsed_seconds=int(fields[2]),
            tres=dict(x.split('=') for x in fields[3].split(',') if x),exit_code=fields[4])
    allocation=accounting['16370']
    if allocation['state']!='COMPLETED' or allocation['tres']['gres/gpu']!='4':
        raise ValueError('whole allocation mismatch')
    rows=[]
    for row in plan['schedule']:
        idx=row['index'];n=read(f'episode-{idx}/native.json')
        if n['job']!='16370' or len(n['gpu_uuids'])!=1 or set(n['gpu_uuids'])&set(service['gpu_uuids']):
            raise ValueError('worker device identity mismatch')
        a=accounting['16370.'+n['step']]
        if a['tres']['gres/gpu']!='1':raise ValueError('worker allocation mismatch')
        t=times[idx]
        if row['arm']!=t['arm'] or row['task']!=t['task']:raise ValueError('timing join mismatch')
        gen=t['returned_generation_seconds']
        if gen>a['elapsed_seconds']+1:raise ValueError('denominator mismatch')
        rows.append(dict(index=idx,**t,step=n['step'],allocated_step_seconds=a['elapsed_seconds'],
            state=a['state'],exit_code=a['exit_code'],
            generation_fraction_of_allocated_step=gen/a['elapsed_seconds']))
    llm=[row for row in rows if row['arm'] in ('continue','reimplement','new_idea')]
    if len(rows)!=18 or len(llm)!=12:raise ValueError('denominator missing')
    total=sum(row['returned_generation_seconds'] for row in llm)
    def describe(group):
        values=[row['generation_fraction_of_allocated_step'] for row in group]
        return dict(n=len(values),median=statistics.median(values),sample_variance=statistics.variance(values),
                    minimum=min(values),maximum=max(values))
    summary=dict(plan_sha256=PLAN_SHA,cost_sha256=COST_SHA,job='16370',source_hashes=hashes,rows=rows,
        allocation=allocation,whole_pool_gpu_hours=allocation['elapsed_seconds']*4/3600,
        returned_generation_gpu_seconds=total,fraction_of_whole_pool_reservation=total/(allocation['elapsed_seconds']*4),
        llm_fraction_of_allocated_step=describe(llm),
        by_task={task:describe([r for r in llm if r['task']==task]) for task in sorted({r['task'] for r in llm})},
        by_arm={arm:describe([r for r in llm if r['arm']==arm]) for arm in sorted({r['arm'] for r in llm})},
        all_worker_gpu_count=1,generator_gpu_count=2,worker_generator_devices_disjoint=True,
        limit='All 12 LLM trajectories including failed/timed-out workers. Slurm elapsed has seconds precision '
              'and includes startup/cleanup; distinct denominator from worker-finished wall time. '
              'Only returned generator calls counted. Reservation windows are not measured idle or savings. '
              'Two reused development tasks; no independent production generalization.')
    path=Path(__file__).with_name('closed_allocation_audit.json')
    encoded=(json.dumps(summary,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if SECRET.search(encoded):raise ValueError('unsafe export')
    with path.open('xb') as f:f.write(encoded)
    print(json.dumps({k:v for k,v in summary.items() if k not in {'source_hashes','rows'}},sort_keys=True))
    print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(encoded).hexdigest())))


if __name__=='__main__':main()
