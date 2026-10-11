"""Outcome-free six-execution diagnostic verification; no model-capacity claim."""
import csv
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from verify_six_gpu_capacity import sha,read,output,difference,overlap

def verify(root,pin,job):
    assert root.name=='resource-execution-six-20261011-v1' and sha(root/'plan.json')==pin
    p=read(root/'plan.json');c=read(root/'closed.json')
    assert read(root/'launch.json')==dict(job=job,plan_sha256=pin)
    expected=[(0,0,0,1),(1,1,0,1)]+[(2+(b-2)*6+s,b,s,6) for b in (2,3) for s in range(6)]
    assert [(r['index'],r['block'],r['slot'],r['width']) for r in p['schedule']]==expected
    assert p['planned']==c['planned']==14 and p['gpus']==6 and p['candidate_seconds']==450 and p['source_seed']==42
    assert {r['program'] for r in p['schedule']}=={1} and p['no_model'] and p['no_api']
    assert p['programs'][1]['source_sha256']==sha(root/'programs/1.py')=='c60e3f1cc3b4613a9707f1c86df12d6d45f1ef36a48ee858b768f9cc8806598d'
    manifest=all(sha(root/n)==h for n,h in p['files'].items());inputs=all(sha(n)==h for n,h in p['input_files'].items())
    returned={x['index']:x for x in c['rows']};assert len(returned)==len(c['rows'])
    with (Path(p['programs'][1]['data'])/'test.csv').open(newline='') as f:
        reader=csv.reader(f);next(reader);ids=[r[0] for r in reader]
    assert len(ids)==len(set(ids))==278640
    rows=[];paths=[];intervals={b:[] for b in range(4)};flags={k:0 for k in ('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')}
    calls=0;warning_coverage=True
    for row in p['schedule']:
        ep=root/f"episode-{row['index']}";done=read(ep/'complete.json') if (ep/'complete.json').exists() else {}
        ex=read(ep/'execution.json') if (ep/'execution.json').exists() else {}
        observations=[read(f) for f in sorted(ep.glob('execute-observation-*.json'))];calls+=len(observations)
        for o in observations:
            assert set(o['flags'])==set(flags)
            for key in flags:flags[key]+=bool(o['flags'][key])
        item=dict(**row,job=job,source_commit=p['source_commit'],source_seed=42,plan_sha256=pin,attempted=row['index'] in returned,
            complete=done.get('complete',False),error_type=done.get('error_type'),candidate_started=(ep/'candidate-start.json').exists(),
            execution_seconds=ex.get('seconds'),timed_out=ex.get('timed_out'),gpu_steps=None,output_sha256=None,observed_execute_calls=len(observations))
        if item['complete']:
            assert returned[row['index']]['returncode']==ex['exit_code']==0 and not ex['timed_out']
            warning_coverage &= len(observations)==3 and {x['call'] for x in observations}=={0,1,2}
            train=read(ep/'gpu-training.json');steps=train['host_step_intervals'];assert train['steps']==len(steps)==588
            assert all(s['devices']==['cuda:0'] and s['gradient_parameters']>0 and s['start']<=s['end'] for s in steps)
            out=ep/'output.private.csv';head,vals=output(out);shape=read(ep/'output-structure.json')
            assert vals.keys()==set(ids) and len(vals)==shape['rows']==278640 and len(head)==shape['columns']
            h=sha(out);assert shape['sha256']==h
            item.update(gpu_steps=588,output_sha256=h);paths.append((row['index'],out,h));intervals[row['block']].append((train['first_step_start'],train['last_step_end']))
        rows.append(item)
    assert sum(x['attempted'] for x in rows)==c['attempted'] and sum(x['complete'] for x in rows)==c['complete']
    blocks=[]
    for b in range(4):
        if not(root/f'block-{b}-go.json').exists():continue
        identities=[read(root/f"episode-{r['index']}/identity.json") for r in p['schedule'] if r['block']==b]
        gpu=set();cpu=set();steps=set()
        for v in identities:
            g=set(v['gpu_uuids']);co={(x['socket'],x['core']) for x in v['cpu_topology']}
            assert v['job']==job and v['step'] not in steps and len(g)==1 and len(co)==4 and not(g&gpu) and not(co&cpu)
            gpu|=g;cpu|=co;steps.add(v['step'])
        blocks.append(dict(block=b,gpus=len(gpu),physical_cores=len(cpu),host_optimizer_envelope_overlap_peak=overlap(intervals[b])))
    pairs=[]
    for (a,pa,ha),(b,pb,hb) in itertools.combinations(paths,2):
        delta=0. if ha==hb else difference(pa,pb)
        pairs.append(dict(left=a,right=b,byte_equal=ha==hb,max_abs_diff=delta,within_tolerance=delta<=1e-5))
    pressure=[json.loads(x) for x in (root/'pressure.jsonl').read_text().splitlines()]
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    a=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==job];assert len(a)==1
    state,seconds,tres=a[0][1:4];assert state not in ('RUNNING','PENDING','COMPLETING')
    assert int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1])==6
    cost=int(seconds)*6;assert cost<=p['gpu_seconds_cap']==10800
    result=dict(job=job,plan_sha256=pin,closed_sha256=sha(root/'closed.json'),manifest_ok=manifest,input_manifest_ok=inputs,
        planned=14,attempted=c['attempted'],complete=c['complete'],unstarted=14-c['attempted'],
        execute_calls_observed=calls,successful_execute_warning_coverage=bool(warning_coverage),resource_error_flags=flags,
        blocks=blocks,comparisons=pairs,uid_threads_peak=max(x['uid_counts']['visible_threads'] for x in pressure),
        nproc_soft_values=sorted({x['limits']['RLIMIT_NPROC'][0] for x in pressure}),after_uid_counts=read(root/'allocation-after.json')['uid_counts'],
        gpu_seconds=cost,gpu_seconds_cap=10800,scheduler_state=state,
        execution_gate=bool(state=='COMPLETED' and c['error_type'] is None and manifest and inputs and c['complete']==14 and len(blocks)==4 and len(pairs)==91
            and all(x['within_tolerance'] for x in pairs) and warning_coverage and not any(flags.values())),
        boundary='Execution-only, one source/seed repeated, no model service. Not2+6 capacity, historical EAGAIN causal proof, speedup or quality.')
    return rows,result

if __name__=='__main__':
    root=Path(sys.argv[1]);pin=sys.argv[2];job=sys.argv[3]
    assert root.parent==Path('/research/d7/spc/yzyang4') and re.fullmatch('[a-f0-9]{64}',pin) and job.isdigit()
    rows,result=verify(root,pin,job)
    with (root/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (root/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k!='comparisons'}))
