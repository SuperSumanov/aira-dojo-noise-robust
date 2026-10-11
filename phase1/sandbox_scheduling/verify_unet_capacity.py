"""Independent narrow single-source capacity gate. Never export predictions."""
from collections import Counter
import csv
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from verify_six_gpu_capacity import sha, read, output, difference, overlap, placement


def verify(root,pin,job):
    assert root.name=='resource-unet-six-capacity-20261011-v2' and sha(root/'plan.json')==pin
    p=read(root/'plan.json');c=read(root/'closed.json');end=read(root/'allocation-closed.json')
    assert read(root/'launch.json')==dict(job=job,plan_sha256=pin)
    expected=[(0,0,0,1),(1,1,0,1)]+[(2+(b-2)*6+s,b,s,6) for b in (2,3) for s in range(6)]
    assert [(r['index'],r['block'],r['slot'],r['width']) for r in p['schedule']]==expected
    assert {r['program'] for r in p['schedule']}=={1} and p['source_families']==1
    assert p['planned']==c['planned']==14 and p['gpus']==8 and p['candidate_seconds']==450 and p['source_seed']==42
    assert p['programs'][1]['source_sha256']=='c60e3f1cc3b4613a9707f1c86df12d6d45f1ef36a48ee858b768f9cc8806598d'
    assert sha(root/'programs/1.py')==p['programs'][1]['source_sha256']
    manifest=all(sha(root/n)==h for n,h in p['files'].items())
    input_manifest=all(sha(n)==h for n,h in p['input_files'].items())
    returned={r['index']:r for r in c['rows']};assert len(returned)==len(c['rows'])
    with (Path(p['programs'][1]['data'])/'test.csv').open(newline='') as f:
        reader=csv.reader(f);next(reader);ids=[r[0] for r in reader]
    assert len(ids)==len(set(ids))
    rows=[];paths=[];requests=[];intervals={b:[] for b in range(4)};blocks=[]
    for r in p['schedule']:
        ep=root/f"episode-{r['index']}";done=read(ep/'complete.json') if (ep/'complete.json').exists() else {}
        ex=read(ep/'execution.json') if (ep/'execution.json').exists() else {}
        req=read(root/f"request-{r['index']}.json") if (root/f"request-{r['index']}.json").exists() else {}
        if req:requests.append(req)
        row=dict(**r,job=job,source_commit=p['source_commit'],source_seed=42,plan_sha256=pin,
            attempted=r['index'] in returned,complete=done.get('complete',False),error_type=done.get('error_type'),
            candidate_started=(ep/'candidate-start.json').exists(),execution_seconds=ex.get('seconds'),timed_out=ex.get('timed_out'),
            gpu_steps=None,output_sha256=None,request_complete=req.get('complete',False),request_finish_reason=req.get('finish_reason'))
        if row['complete']:
            assert ex['exit_code']==returned[r['index']]['returncode']==0 and not ex['timed_out']
            train=read(ep/'gpu-training.json');steps=train['host_step_intervals'];assert train['steps']==len(steps)==588
            assert all(s['devices']==['cuda:0'] and s['gradient_parameters']>0 and s['start']<=s['end'] for s in steps)
            out=ep/'output.private.csv';head,vals=output(out);shape=read(ep/'output-structure.json')
            assert set(ids)==vals.keys() and len(vals)==shape['rows']==278640 and len(head)==shape['columns']
            h=sha(out);assert shape['sha256']==h
            row.update(gpu_steps=588,output_sha256=h);paths.append((r['index'],out,h))
            intervals[r['block']].append((train['first_step_start'],train['last_step_end']))
        rows.append(row)
    assert sum(r['attempted'] for r in rows)==c['attempted'] and sum(r['complete'] for r in rows)==c['complete']
    assert len(requests)==c['requests_attempted'] and sum(r['complete'] for r in requests)==c['requests_complete']
    for b in range(4):
        if not(root/f'block-{b}-go.json').exists():continue
        ident=[read(root/f"episode-{r['index']}/identity.json") for r in p['schedule'] if r['block']==b]
        checked=placement(read(root/'service-identity.json'),read(root/'service-cpu.json'),ident,job)
        blocks.append(dict(block=b,**checked,host_optimizer_envelope_overlap_peak=overlap(intervals[b])))
    pairs=[]
    for (a,pa,ha),(b,pb,hb) in itertools.combinations(paths,2):
        d=0. if ha==hb else difference(pa,pb)
        pairs.append(dict(left=a,right=b,byte_equal=ha==hb,max_abs_diff=d,within_frozen_tolerance=d<=1e-5))
    pressure=[json.loads(x) for x in (root/'pressure.jsonl').read_text().splitlines()]
    flags={k:0 for k in ('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')}
    for path in [root/'service.private.log']+list(root.glob('episode-*/worker.private.log'))+list(root.glob('episode-*/execution.private.txt')):
        text=path.read_text(errors='replace').lower() if path.exists() else ''
        for k in flags:flags[k]+=text.count(k)
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-j',job,'-X','-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    acc=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==job];assert len(acc)==1
    state,seconds,tres=acc[0][1:4];assert state not in ('RUNNING','COMPLETING','PENDING')
    assert int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1])==8
    cost=int(seconds)*8;assert cost<=p['gpu_seconds_cap']==19200
    summary=dict(job=job,plan_sha256=pin,closed_sha256=sha(root/'closed.json'),manifest_ok=manifest,input_manifest_ok=input_manifest,planned=14,
        attempted=c['attempted'],complete=c['complete'],unstarted=14-c['attempted'],requests_attempted=len(requests),requests_complete=c['requests_complete'],
        requests_finish_reason=dict(Counter(x.get('finish_reason','error') for x in requests)),
        request_host_overlap_peak=overlap([(r['start'],r['end']) for r in requests]),
        blocks=blocks,comparisons=pairs,all_same_source=True,independent_source_families=1,seed_restarts_not_new_seeds=True,
        resource_error_markers=flags,uid_threads_peak=max(x['uid_counts']['visible_threads'] for x in pressure),
        nproc_soft_values=sorted({x['limits']['RLIMIT_NPROC'][0] for x in pressure}),
        after_uid_counts=read(root/'allocation-after.json')['uid_counts'],service_stopped=end['service_stopped'],
        gpu_seconds=cost,gpu_seconds_cap=19200,scheduler_state=state,
        narrow_capacity_gate=bool(manifest and input_manifest and state=='COMPLETED' and c['complete']==c['requests_complete']==14 and len(pairs)==91
            and all(x['within_frozen_tolerance'] for x in pairs) and len(blocks)==4 and not any(flags.values()) and end['returncode']==0 and end['service_stopped']),
        boundary='Post-failure fast UNet-only capacity check. Cannot rescue two-family failure, generalize to six tasks or heavy agent generation, infer historical EAGAIN cause, speedup or quality.')
    return rows,summary


if __name__=='__main__':
    root=Path(sys.argv[1]);pin=sys.argv[2];job=sys.argv[3]
    assert root.parent==Path('/research/d7/spc/yzyang4') and re.fullmatch('[a-f0-9]{64}',pin) and job.isdigit()
    rows,result=verify(root,pin,job)
    with (root/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (root/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:v for k,v in result.items() if k!='comparisons'}))
