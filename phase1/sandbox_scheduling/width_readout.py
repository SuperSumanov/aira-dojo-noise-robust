"""Frozen width-study readout, complete denominator and independent admission replay."""
import json
import os
import re
import statistics
import subprocess
from lifecycle_pilot import read,write,sha
from live_identity import cores
from verify_pool_outputs import strict
from width_contract import WIDTHS,schedule


def peak(intervals):
    events=sorted([(a,1) for a,b in intervals]+[(b,-1) for a,b in intervals])
    active=maximum=0
    for t,delta in events:
        active+=delta;maximum=max(maximum,active)
        if active<0:raise ValueError('invalid interval')
    if active:raise ValueError('open interval')
    return maximum


def summarize_ratios(blocks):
    answer={}
    for numerator,denominator in (('pipeline','share2'),('pipeline','share4'),('share2','share4')):
        pairs=[]
        for repeat in range(3):
            own={b['arm']:b for b in blocks if b['repeat']==repeat and b['completed']==4}
            value=own[numerator]['makespan']/own[denominator]['makespan'] if {numerator,denominator}<=own.keys() else None
            pairs.append(value)
        full=all(v is not None for v in pairs)
        answer[numerator+'_over_'+denominator]=dict(paired=pairs,
            median=statistics.median(pairs) if full else None,
            sample_std=statistics.stdev(pairs) if full else None)
    return answer


def main():
    import neural_width_trial as trial
    root=trial.R;plan=trial.check();closed=read(root/'closed.json');runs=read(root/'runs.json')
    job=read(root/'launch.json')['job']
    if [r['index'] for r in runs]!=list(range(36)):raise ValueError('full denominator')
    if [{k:r[k] for k in s} for r,s in zip(runs,schedule())]!=schedule():raise ValueError('matrix drift')
    raw=subprocess.check_output(['sacct','-X','-n','-P','-j',str(job),'--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],
        env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
    matches=[r.split('|') for r in raw.splitlines() if r.split('|')[0]==str(job)]
    if len(matches)!=1 or matches[0][1] not in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY'):
        raise ValueError('terminal allocation required')
    allocation=matches[0];tres=dict(s.split('=',1) for s in allocation[3].split(',') if '=' in s)
    if tres.get('cpu')!='6' or tres.get('gres/gpu')!='1':raise ValueError('allocation resources')
    native=read(root/'allocation.json');identity_ok=len(cores(native['cpu_topology']))==6
    outputs=set();references={};equal={0:True,1:True};steps={};intervals={};stages=[]
    for r in runs:
        ep=root/f'episode-{r["index"]}'
        if (ep/'native.json').exists():
            w=read(ep/'native.json');started=read(ep/'started.json')
            identity_ok &= w['job']==native['job'] and w['gpu_uuids']==[native['gpu_uuid']] and started['affinity']==native['affinity']
        if r['status']!='complete':continue
        done=read(ep/'completed.json');closing=read(ep/'closed.json');path=ep/'work/submission.csv'
        if not done['complete'] or closing['returncode'] or sha(path)!=r['output_sha256'] or sha(path)!=done['output']['sha256']:
            raise ValueError('completion/output identity')
        ready=read(ep/'prelude_ready.json')['time'];admit=read(ep/'execution_admitted.json')['time']
        begin=read(ep/'candidate_started.json')['time'];end=read(ep/'candidate_ended.json')['time']
        if not done['start']<=ready<=admit<=begin<=end<=done['end']<=closing['end']:
            raise ValueError('lifecycle timing')
        intervals[r['index']]=(admit,closing['end'])
        current=strict(path);program=r['program']
        if program not in references:references[program]=current
        else:equal[program] &= current==references[program]
        outputs.add(r['index']);steps[r['index']]=done['gpu_training']['steps']
        stages.append(dict(index=r['index'],startup=ready-done['start'],queue=admit-ready,candidate=end-begin,return_seconds=done['end']-done['start']))
    equivalence=[]
    for program,expected_steps in ((0,150),(1,640)):
        own=[r for r in runs if r['program']==program and r['index'] in outputs]
        equivalence.append(dict(program=program,present=len(own),expected=18,
            exact_numeric_equal=len(own)==18 and equal[program],
            original_steps_preserved=len(own)==18 and all(steps[r['index']]==expected_steps for r in own)))
    blocks=[];structure=True
    for block in range(9):
        path=root/f'block-{block}.json'
        if not path.exists():continue
        rec=read(path);own=runs[block*4:block*4+4];spans=[intervals[r['index']] for r in own if r['index'] in intervals]
        samples=read(root/f'telemetry-{block}.json');all_ready=[];admissions=[];ports=[]
        for r in own:
            ep=root/f'episode-{r["index"]}'
            if (ep/'prelude_ready.json').exists():all_ready.append(read(ep/'prelude_ready.json')['time'])
            if (ep/'execution_admitted.json').exists():admissions.append((read(ep/'execution_admitted.json')['time'],r['index']))
            log=ep/'worker.private.log'
            announced=re.findall(r'is available at http://[^:\s]+:(\d+)',log.read_text(errors='replace')) if log.exists() else []
            ports.append(int(announced[0]) if len(announced)==1 else None)
        full=len(spans)==4
        admission_ok=full and len(all_ready)==4 and len(admissions)==4 and min(t for t,i in admissions)>=max(all_ready)
        admission_ok &= [i for t,i in sorted(admissions)]==[r['index'] for r in own]
        admission_ok &= peak(spans)<=WIDTHS[rec['arm']]
        port_ok=None not in ports and len(set(ports))==4
        structure &= admission_ok and port_ok and not rec['telemetry_errors']
        returns=[read(root/f'episode-{r["index"]}/completed.json')['end']-rec['start'] for r in own if r['status']=='complete']
        blocks.append(dict(block=block,arm=rec['arm'],repeat=rec['repeat'],makespan=rec['end']-rec['start'],
            completed=len(spans),admission_verified=bool(admission_ok),peak_execution_leases=peak(spans),
            announced_gateway_ports_disjoint=port_ok,
            first_return_seconds=min(returns) if returns else None,mean_return_seconds=statistics.mean(returns) if full else None,
            last_return_seconds=max(returns) if returns else None,
            telemetry_samples=len(samples),peak_resident_gpu_clients=max((len(s['apps']) for s in samples),default=None),
            peak_gpu_memory_mib=max((s['memory_mib'] for s in samples),default=None)))
    valid=bool(len(blocks)==9 and structure and identity_ok and all(e['exact_numeric_equal'] and e['original_steps_preserved'] for e in equivalence)
        and closed['controller_error'] is None and allocation[1]=='COMPLETED' and int(allocation[2])<=plan['allocation_seconds'])
    result=dict(job=job,source_commit=plan['source_commit'],plan_sha256=sha(root/'plan.json'),readout_source_sha256=sha(__file__),
        closed_sha256=sha(root/'closed.json'),assigned=36,attempted=closed['attempted'],complete=closed['completed'],
        allocation_state=allocation[1],allocation_exit=allocation[4],allocation_gpu_seconds=int(allocation[2]),
        allocation_gpu_hours=int(allocation[2])/3600,complete_valid_comparison=valid,
        ratios=summarize_ratios(blocks),blocks=blocks,output_equivalence=equivalence,stages=stages,
        CPU_GPU_identity_verified=bool(identity_ok),controller_error=closed['controller_error'],
        boundary='Two reused neural programs, two copies each, same seed42, three scheduling repeats. Exact outputs and steps are not quality/generalization. Resident GPU clients are not concurrent kernels. All failures retained; incomplete ratios are descriptive, not a rescued comparison.')
    out=root/'readout-v1';out.mkdir(mode=0o700,exist_ok=False);write(out/'summary.json',result)
    print(json.dumps({k:result[k] for k in ('job','assigned','attempted','complete','complete_valid_comparison','ratios','allocation_gpu_seconds')}))


if __name__=='__main__':main()
