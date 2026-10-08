"""Full 24-slot homogeneous contention readout; no labels or raw value export."""
import csv
import itertools
import json
import os
import subprocess

from homogeneous_trial import R,schedule
from lifecycle_pilot import read,write,sha
from throughput_readout import difference,distribution,overlap
from verify_pool_outputs import strict


def main():
    plan=read(R/'plan.json');job=read(R/'launch.json')['job']
    raw=subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],
                                env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
    matched=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    if len(matched)!=1 or matched[0][1] in ('PENDING','RUNNING','COMPLETING'):raise ValueError('not terminal')
    alloc=matched[0];tres=dict(v.split('=',1) for v in alloc[3].split(',') if '=' in v)
    if int(tres['gres/gpu'])!=1 or int(tres['cpu'])!=6:raise ValueError('resource contract')
    runs=[];outputs={};envelopes={};receipts=[]
    for row in schedule():
        ep=R/f'episode-{row["index"]}';r=dict(**row,status='not_started',source_commit=plan['source_commit'])
        if (ep/'started.json').exists():r['status']='incomplete'
        if (ep/'closed.json').exists():r.update(read(ep/'closed.json'));r['status']='failed'
        if (ep/'completed.json').exists():
            done=read(ep/'completed.json');r.update({k:v for k,v in done.items() if k not in ('output','gpu_training')})
            if done['complete'] and r.get('returncode')==0:
                r['status']='complete';output=ep/'work/submission.csv'
                if sha(output)!=done['output']['sha256']:raise ValueError('output drift')
                outputs[r['index']]=strict(output);r['output_sha256']=sha(output)
                train=read(ep/'work/gpu_training.json')
                if train!=done['gpu_training']:raise ValueError('training receipt drift')
                steps=train['host_step_intervals'];r['gpu_steps']=train['steps']
                start=read(ep/'candidate_started.json')['time'];end=read(ep/'candidate_ended.json')['time']
                if not steps or len(steps)!=train['steps'] or any(s['devices']!=['cuda:0'] or s['gradient_parameters']<=0 or not start<=s['start']<=s['end']<=end for s in steps):raise ValueError('GPU/step contract')
                envelopes[r['index']]=(steps[0]['start'],steps[-1]['end'])
                receipts.append(dict(index=r['index'],program=r['program'],arm=r['arm'],repeat=r['repeat'],replica=r['replica'],steps=len(steps),
                                     before_first_step=steps[0]['start']-start,optimizer_span=steps[-1]['end']-steps[0]['start'],after_last_step=end-steps[-1]['end'],
                                     host_optimizer_envelope_not_kernel_time=True))
        runs.append(r)
    blocks=[]
    for b in range(12):
        path=R/f'block-{b}.json'
        if not path.exists():continue
        block=read(path);own=runs[2*b:2*b+2];spans=[]
        for r in own:
            ep=R/f'episode-{r["index"]}'
            if (ep/'candidate_started.json').exists() and (ep/'candidate_ended.json').exists():
                spans.append((read(ep/'candidate_started.json')['time'],read(ep/'candidate_ended.json')['time']))
        samples=read(R/f'telemetry-{b}.json');optim=[envelopes[r['index']] for r in own if r['index'] in envelopes]
        blocks.append(dict(block=b,program=block['program'],repeat=block['repeat'],arm=block['arm'],seconds=block['end']-block['start'],
                           completed=sum(r['status']=='complete' for r in own),candidate_overlap=overlap(spans),
                           optimizer_envelope_overlap=overlap(optim),not_kernel_concurrency_measurement=True,
                           gpu_peak_memory_mib=max((s['memory_mib'] for s in samples),default=None),
                           max_resident_gpu_clients=max((len(s['apps']) for s in samples),default=None),
                           multi_client_samples=sum(len(s['apps'])>1 for s in samples),telemetry_samples=len(samples)))
    per_task=[]
    for program in (0,1):
        ratios=[]
        for rep in range(3):
            own={b['arm']:b for b in blocks if b['program']==program and b['repeat']==rep}
            if set(own)=={'serial','share2'} and all(b['completed']==2 for b in own.values()):
                ratios.append(dict(repeat=rep,ratio=own['serial']['seconds']/own['share2']['seconds']))
        own=[r for r in runs if r['program']==program and r['index'] in outputs]
        pairs=[dict(indices=[a['index'],b['index']],arms=[a['arm'],b['arm']],**difference(outputs[a['index']],outputs[b['index']]))
               for a,b in itertools.combinations(own,2)]
        within=max((p['max_abs'] for p in pairs if p['arms'][0]==p['arms'][1]),default=None)
        cross=max((p['max_abs'] for p in pairs if p['arms'][0]!=p['arms'][1]),default=None)
        counts=[r['gpu_steps'] for r in own];speed=distribution([r['ratio'] for r in ratios])
        numeric=(cross<=within+1e-6 and cross<=1e-5) if len(own)==12 else None
        equal_steps=len(set(counts))==1 if len(own)==12 else None
        per_task.append(dict(program=program,task=plan['programs'][program]['task'],completed=len(own),
                             paired_ratios=ratios,speedup=speed,steps=counts,step_counts_equal=equal_steps,
                             pairs=pairs,max_within_arm=within,max_cross_arm=cross,numerical_gate=numeric,
                             exploratory_gate=len(own)==12 and len(ratios)==3 and speed['median']>=1.05 and equal_steps and numeric))
    result=dict(job=job,source_commit=plan['source_commit'],plan_sha256=sha(R/'plan.json'),planned=24,
                attempted=sum(r['status']!='not_started' for r in runs),completed=sum(r['status']=='complete' for r in runs),
                allocation_state=alloc[1],allocation_exit=alloc[4],allocation_seconds=int(alloc[2]),
                whole_pool_gpu_hours=int(alloc[2])/3600,within_cap=int(alloc[2])<=5400,
                blocks=blocks,per_task=per_task,training_receipts=receipts,runs=runs,
                boundary='Deliberate identical-code contention, two fixed public-derived tasks. Same-source-seed restarts are not independent seeds. No pooled task effect, quality score, novel method or live search.')
    dest=R/'readout-v1';dest.mkdir(mode=0o700,exist_ok=False);write(dest/'summary.json',result)
    with (dest/'runs.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sorted({k for r in runs for k in r}));w.writeheader();w.writerows(runs)
    print(json.dumps(dict(job=job,planned=24,completed=result['completed'],allocation_seconds=result['allocation_seconds'],
                         per_task=[{k:r[k] for k in ('program','completed','speedup','step_counts_equal','numerical_gate','exploratory_gate')} for r in per_task],summary_sha256=sha(dest/'summary.json')),sort_keys=True))


if __name__=='__main__':main()
