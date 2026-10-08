"""Fixed pipeline comparison, all 36 slots; remote numerical aggregates only."""
import itertools
import json
import os
import subprocess

from lifecycle_pilot import read,write,sha
from pipeline_trial import R,schedule,PROGRAMS,predecessor
from throughput_readout import difference,distribution,overlap
from verify_pool_outputs import strict


def main():
    plan=read(R/'plan.json');job=read(R/'launch.json')['job']
    raw=subprocess.check_output(['sacct','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],
                                env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=20)
    matching=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    if len(matching)!=1 or matching[0][1] in ('RUNNING','PENDING','COMPLETING'):raise ValueError('not terminal')
    alloc=matching[0];tres=dict(v.split('=',1) for v in alloc[3].split(',') if '=' in v)
    if int(tres['gres/gpu'])!=1 or int(tres['cpu'])!=6:raise ValueError('resource contract')
    runs=read(R/'runs.json')
    if [r['index'] for r in runs]!=list(range(36)):raise ValueError('denominator')
    outputs={};stages=[]
    for r in runs:
        if r['status']!='complete':continue
        ep=R/f'episode-{r["index"]}';done=read(ep/'completed.json');path=ep/'work/submission.csv'
        if sha(path)!=r['output_sha256'] or sha(path)!=done['output']['sha256']:raise ValueError('output drift')
        outputs[r['index']]=strict(path)
        ready=read(ep/'prelude_ready.json')['time'];admit=read(ep/'execution_admitted.json')['time']
        start=read(ep/'candidate_started.json')['time'];end=read(ep/'candidate_ended.json')['time']
        if not done['start']<=ready<=admit<=start<=end<=done['end']:raise ValueError('stage ordering')
        previous=predecessor(r)
        if previous is not None and read(R/f'episode-{previous}/closed.json')['end']>admit:raise ValueError('pipeline overlap violation')
        stages.append(dict(index=r['index'],arm=r['arm'],program=r['program'],repeat=r['repeat'],
                           startup=ready-done['start'],queue=admit-ready,candidate=end-start,after_candidate=done['end']-end,
                           gpu_fit_receipt=done.get('gpu_training')))
    blocks=[]
    for b in range(9):
        path=R/f'block-{b}.json'
        if not path.exists():continue
        record=read(path);own=runs[4*b:4*b+4];spans=[]
        for r in own:
            ep=R/f'episode-{r["index"]}'
            if (ep/'candidate_started.json').exists() and (ep/'candidate_ended.json').exists():
                spans.append((read(ep/'candidate_started.json')['time'],read(ep/'candidate_ended.json')['time']))
        sharing=overlap(spans)
        if record['arm'] in ('serial','pipeline') and sharing['max_simultaneous']>1:raise ValueError('execution overlap invariant')
        samples=read(R/f'telemetry-{b}.json')
        blocks.append(dict(block=b,arm=record['arm'],repeat=record['repeat'],seconds=record['end']-record['start'],
                           completed=sum(r['status']=='complete' for r in own),candidate_overlap=sharing,
                           max_resident_gpu_clients=max((len(s['apps']) for s in samples),default=None),
                           not_kernel_concurrency_measurement=True))
    equivalence=[]
    for program in PROGRAMS:
        own=[r for r in runs if r['program']==program and r['index'] in outputs]
        pairs=[dict(indices=[a['index'],b['index']],arms=[a['arm'],b['arm']],**difference(outputs[a['index']],outputs[b['index']]))
               for a,b in itertools.combinations(own,2)]
        fits=[v['gpu_fit_receipt'] for v in stages if v['program']==program]
        # GPU fit device/backend/rounds are compared, not timing fields.
        fit_counts=[[{k:v for k,v in receipt.items() if k in ('backend','device','rounds')} for receipt in row] if row else None for row in fits]
        equivalence.append(dict(program=program,outputs=len(own),pairs=pairs,
                                exact_numerical_equality=all(p['max_abs']==0 for p in pairs) if len(own)==9 else None,
                                same_fit_rounds=all(v==fit_counts[0] for v in fit_counts) if len(own)==9 else None))
    ratios={}
    for a,b in (('serial','pipeline'),('serial','share2'),('pipeline','share2')):
        pairs=[]
        for rep in range(3):
            own={r['arm']:r for r in blocks if r['repeat']==rep}
            if a in own and b in own and own[a]['completed']==own[b]['completed']==4:
                pairs.append(dict(repeat=rep,ratio=own[a]['seconds']/own[b]['seconds']))
        ratios[a+'_over_'+b]=dict(pairs=pairs,distribution=distribution([p['ratio'] for p in pairs]))
    result=dict(job=job,source_commit=plan['source_commit'],plan_sha256=sha(R/'plan.json'),planned=36,
                attempted=sum(r['status']!='not_started' for r in runs),completed=sum(r['status']=='complete' for r in runs),
                allocation_state=alloc[1],allocation_exit=alloc[4],allocation_seconds=int(alloc[2]),
                whole_pool_gpu_hours=int(alloc[2])/3600,within_cap=int(alloc[2])<=2700,
                blocks=blocks,stages=stages,ratios=ratios,output_equivalence=equivalence,runs=runs,
                boundary='Small fixed public-development programs, same-source-seed restarts. No quality score, novel method, or live E2E inference.')
    out=R/'readout-v1';out.mkdir(mode=0o700,exist_ok=False);write(out/'summary.json',result)
    print(json.dumps({k:result[k] for k in ('job','planned','attempted','completed','allocation_seconds','whole_pool_gpu_hours','ratios')},sort_keys=True))


if __name__=='__main__':main()
