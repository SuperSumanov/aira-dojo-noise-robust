"""Independent readout of the frozen 2+6 capacity gate, never task quality.

Private numeric outputs stay remote. Exports hashes, maximum discrepancies,
fixed structural checks and the entire planned denominator, including failures.
Does not import the experiment driver or change its frozen acceptance criteria.
"""
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def topology(rows):
    assert rows and len({x['logical_cpu'] for x in rows}) == len(rows)
    return {(x['socket'], x['core']) for x in rows}


def placement(service, service_cpu, identities, job):
    gpu = set(service['uuids']); cpu = topology(service_cpu)
    assert len(gpu) == 2 and len(cpu) == 8
    steps = {service['step']}
    for item in identities:
        g = set(item['gpu_uuids']); c = topology(item['cpu_topology'])
        assert len(g) == 1 and len(c) == 4 and not g & gpu and not c & cpu
        assert item['job'] == job and item['step'] not in steps
        gpu |= g; cpu |= c; steps.add(item['step'])
    return {'gpus': len(gpu), 'physical_cores': len(cpu)}


def output(path):
    with Path(path).open(newline='') as f:
        reader = csv.reader(f); header = next(reader); values = {}
        assert len(header) >= 2 and len(set(header)) == len(header)
        for row in reader:
            assert len(row) == len(header) and row[0] not in values
            v = tuple(float(x) for x in row[1:])
            assert all(math.isfinite(x) for x in v)
            values[row[0]] = v
    return header, values


def difference(left, right):
    ha, a = output(left); hb, b = output(right)
    assert ha == hb and a.keys() == b.keys()
    return max((abs(x-y) for k in a for x, y in zip(a[k], b[k])), default=0.)


def overlap(intervals):
    events = [(a, 1) for a, b in intervals if b > a] + [(b, -1) for a, b in intervals if b > a]
    active = peak = 0
    for _, delta in sorted(events):
        active += delta; peak = max(active, peak)
    return peak


def verify(root, pin, job):
    assert sha(root/'plan.json') == pin
    p = read(root/'plan.json'); close = read(root/'closed.json'); end = read(root/'allocation-closed.json')
    launch = read(root/'launch.json')
    assert launch['job'] == job and launch['plan_sha256'] == pin
    expected = [(0,0,0,0,1),(1,1,0,1,1)]
    expected += [(2+(b-2)*6+s,b,s,(s+b)%2,6) for b in (2,3) for s in range(6)]
    assert [(r['index'],r['block'],r['slot'],r['program'],r['width']) for r in p['schedule']] == expected
    assert p['planned'] == close['planned'] == 14 and p['gpus'] == 8
    assert p['candidate_seconds'] == 450 and p['source_seed'] == 42
    manifest_ok = all(sha(root/n) == h for n,h in p['files'].items())
    results = {r['index']:r for r in close['rows']}; assert len(results) == len(close['rows'])
    records=[]; output_paths={0:[],1:[]}; intervals={b:[] for b in range(4)}
    requests=[]; shapes=[]
    for r in p['schedule']:
        ep=root/f"episode-{r['index']}"
        c=read(ep/'complete.json') if (ep/'complete.json').exists() else {}
        e=read(ep/'execution.json') if (ep/'execution.json').exists() else {}
        t=read(ep/'gpu-training.json') if (ep/'gpu-training.json').exists() else {}
        req=read(root/f"request-{r['index']}.json") if (root/f"request-{r['index']}.json").exists() else {}
        if req: requests.append(req)
        row=dict(**r,job=job,plan_sha256=pin,source_commit=p['source_commit'],source_seed=42,
            attempted=r['index'] in results,candidate_started=(ep/'candidate-start.json').exists(),
            complete=c.get('complete',False),error_type=c.get('error_type'),returncode=results.get(r['index'],{}).get('returncode'),
            execution_seconds=e.get('seconds'),gpu_steps=t.get('steps'),cuda_gradient_receipt=False,
            request_complete=req.get('complete',False),request_finish_reason=req.get('finish_reason'),
            request_seconds=(req['end']-req['start']) if req else None,output_sha256=None)
        if c.get('complete'):
            assert row['returncode']==e['exit_code']==0 and not e['timed_out']
            steps=t['host_step_intervals']; assert steps and len(steps)==t['steps']
            assert all(x['devices']==['cuda:0'] and x['gradient_parameters']>0 and x['start']<=x['end'] for x in steps)
            row['cuda_gradient_receipt']=True
            out=ep/'output.private.csv'; head,values=output(out)
            q=Path(p['programs'][r['program']]['data'])/'test.csv'
            with q.open(newline='') as f:
                reader=csv.reader(f); next(reader); ids=[x[0] for x in reader]
            assert len(set(ids))==len(ids)==len(values) and set(ids)==values.keys()
            shape=read(ep/'output-structure.json'); row['output_sha256']=sha(out)
            assert shape['sha256']==row['output_sha256'] and shape['rows']==len(values) and shape['columns']==len(head)
            output_paths[r['program']].append((r['index'],out,row['output_sha256']))
            shapes.append({'index':r['index'],'rows':len(values),'columns':len(head)})
            intervals[r['block']].append((t['first_step_start'],t['last_step_end']))
        records.append(row)
    assert sum(r['attempted'] for r in records)==close['attempted']
    assert sum(r['complete'] for r in records)==close['complete']
    assert len(requests)==close['requests_attempted']
    assert sum(r['request_complete'] for r in records)==close['requests_complete']
    blocks=[]
    if (root/'service-identity.json').exists() and (root/'service-cpu.json').exists():
        for b in range(4):
            go=root/f'block-{b}-go.json'
            if not go.exists(): continue
            ids=[read(root/f"episode-{r['index']}/identity.json") for r in p['schedule'] if r['block']==b]
            checked=placement(read(root/'service-identity.json'),read(root/'service-cpu.json'),ids,job)
            blocks.append({'block':b,**checked,'host_optimizer_envelope_overlap_peak':overlap(intervals[b])})
    comparisons=[]
    for program, paths in output_paths.items():
        for (a,pa,ha),(b,pb,hb) in itertools.combinations(paths,2):
            diff=0. if ha==hb else difference(pa,pb)
            comparisons.append(dict(program=program,left=a,right=b,byte_equal=ha==hb,max_abs_diff=diff,within_frozen_tolerance=diff<=1e-5))
    pressure=[]
    for line in (root/'pressure.jsonl').read_text().splitlines(): pressure.append(json.loads(line))
    after=read(root/'allocation-after.json'); counts=after['uid_counts']
    categories=('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')
    markers={k:0 for k in categories}
    for path in [root/'service.private.log']+list(root.glob('episode-*/worker.private.log')):
        raw=path.read_text(errors='replace').lower() if path.exists() else ''
        for k in categories: markers[k]+=raw.count(k)
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-j',job,'-X','-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    account=[l.split('|') for l in raw.splitlines() if l.split('|')[0]==job]; assert len(account)==1
    state,seconds,tres=account[0][1:4]; assert state not in ('PENDING','RUNNING','COMPLETING')
    gpus=int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1]); assert gpus==8
    cost=int(seconds)*gpus; assert cost<=p['gpu_seconds_cap']
    summary=dict(job=job,plan_sha256=pin,closed_sha256=sha(root/'closed.json'),manifest_ok=manifest_ok,
        planned=14,attempted=close['attempted'],complete=close['complete'],unstarted=14-close['attempted'],
        candidate_started=sum(r['candidate_started'] for r in records),requests_attempted=len(requests),requests_complete=close['requests_complete'],
        cuda_gradient_receipts=sum(r['cuda_gradient_receipt'] for r in records),blocks=blocks,output_shapes=shapes,
        comparisons=comparisons,numerical_tolerance=1e-5,private_predictions_exported=False,
        pressure_rows=len(pressure),host_uid_threads_peak=max(x['uid_counts']['visible_threads'] for x in pressure),
        host_uid_threads_are_visible_lower_bounds=True,nproc_soft_values=sorted({x['limits']['RLIMIT_NPROC'][0] for x in pressure}),
        available_memory_min_gib=min(x['available_memory_kib'] for x in pressure)/1024**2,
        after_uid_counts=counts,resource_error_marker_counts=markers,scheduler_state=state,
        gpu_seconds=cost,gpu_seconds_cap=p['gpu_seconds_cap'],service_stopped=end['service_stopped'],
        qualification='Two fixed public-data source families, seed42 restarts; capacity acceptance, not production agent/search quality or causal scheduling speedup.')
    summary['full_capacity_gate']=bool(manifest_ok and state=='COMPLETED' and close['complete']==close['requests_complete']==14
        and summary['cuda_gradient_receipts']==14 and len(blocks)==4 and len(comparisons)==42
        and all(x['within_frozen_tolerance'] for x in comparisons) and not any(markers.values())
        and end['returncode']==0 and end['service_stopped'])
    return records,summary


if __name__=='__main__':
    root=Path(sys.argv[1]);pin=sys.argv[2];job=sys.argv[3]
    assert root.parent==Path('/research/d7/spc/yzyang4') and root.name.startswith('resource-six-gpu-capacity-')
    assert re.fullmatch('[a-f0-9]{64}',pin) and job.isdigit()
    rows,result=verify(root,pin,job)
    with (root/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with (root/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('comparisons','output_shapes')}))
