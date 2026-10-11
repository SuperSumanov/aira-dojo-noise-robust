"""Independent two-node acceptance. Numeric public-fixture outputs stay remote."""
import collections,csv,inspect,json,os,re,subprocess,sys
from pathlib import Path
import verify_six_gpu_capacity as v
from execution_exit_readout_20261011 import events

ROOT=Path('/research/d7/spc/yzyang4/resource-joint-two-node-20261011-v1')
FLAGS=('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')

def placed(service,service_cpu,identities,job):
    gpu=set(service['uuids']);steps={service['step']}
    cpu={(x['node'],x['socket'],x['core']) for x in service_cpu}
    assert len(gpu)==2 and len(cpu)==8 and {x[0] for x in cpu}=={'gpu3'}
    for identity in identities:
        g=set(identity['gpu_uuids']);c={(x['node'],x['socket'],x['core']) for x in identity['cpu_topology']}
        assert len(g)==1 and len(c)==4 and not g&gpu and not c&cpu
        assert identity['job']==job and identity['step'] not in steps
        assert len({x[0] for x in c})==1 and {x[0] for x in c}<={'gpu3','gpu27'}
        gpu|=g;cpu|=c;steps.add(identity['step'])
    return dict(gpus=len(gpu),physical_cores=len(cpu),nodes=sorted({x[0] for x in cpu}))

def audit(pin,job):
    assert v.sha(ROOT/'plan.json')==pin
    p=v.read(ROOT/'plan.json')
    assert p['gpus']==8 and p['cpus']==40 and p['nodes']==['gpu3','gpu27'] and p['gpu_seconds_cap']==19200
    if not (ROOT/'closed.json').exists():
        raise RuntimeError('Missing controller closure: reconcile full14 denominator before any success claim')
    scope=dict(v.__dict__,placement=placed)
    exec(compile(inspect.getsource(v.verify),'frozen-independent-two-node-readout','exec'),scope)
    rows,result=scope['verify'](ROOT,pin,job)
    coverage=True;clean=True;steps=True;placement_ok=True;flags={x:0 for x in FLAGS}
    lifecycle=[]
    for row in rows:
        ep=ROOT/f"episode-{row['index']}";planned=p['schedule'][row['index']]
        expected_node='gpu3' if (row['block']==0 or row['block']>=2 and row['slot']<2) else 'gpu27'
        assert planned['node']==expected_node
        if (ep/'identity.json').exists():placement_ok &= {x['node'] for x in v.read(ep/'identity.json')['cpu_topology']}=={expected_node}
        calls=[v.read(x) for x in ep.glob('execute-observation-*.json')]
        for call in calls:
            assert set(call['flags'])==set(flags)
            for k in flags:flags[k]+=bool(call['flags'][k])
        ev=events(ep)
        if row['complete']:
            coverage &= len(calls)==3 and {x['call'] for x in calls}=={0,1,2}
            steps &= row['gpu_steps']==(150 if row['program']==0 else 588)
        if row['candidate_started']:
            installed=v.read(ep/'kernel-shutdown-guard-installed.json')
            coverage &= installed==dict(original_sha256='aaaee97aa5b9c52ae47c68f8503468153da8d2a6f0b8bd0756f55e5b14bb6c7e',transition_timeout=15,no_candidate_retry=True)
            coverage &= any(x['event']=='launched' for x in ev)
        text=(ep/'worker.private.log').read_text(errors='replace') if (ep/'worker.private.log').exists() else ''
        cleanup=dict(http500=bool(re.search(r'\b500 DELETE /api/kernels/',text)),invalid_state='InvalidStateError' in text,forced_kill='did not terminate; sending SIGKILL' in text)
        clean &= not any(cleanup.values())
        lifecycle.append(dict(index=row['index'],events=ev,cleanup_flags=cleanup,execute_calls=len(calls)))
    second=[json.loads(line) for line in (ROOT/'gpu27-pressure.jsonl').read_text().splitlines()]
    assert second and all(x['host'].split('.')[0]=='gpu27' for x in second)
    times=[x['time_utc_seconds'] for x in second]
    second_coverage=[]
    for b in (2,3):
        go=ROOT/f'block-{b}-go.json'
        if not go.exists():continue
        start=v.read(go)['time'];ends=[v.read(ROOT/f"episode-{r['index']}/complete.json")['end'] for r in p['schedule'] if r['block']==b and (ROOT/f"episode-{r['index']}/complete.json").exists()]
        nearby=[t for t in times if start-5<=t<=max(ends,default=start)+5]
        ok=bool(nearby and nearby[0]<=start and nearby[-1]>=max(ends,default=start) and max([right-left for left,right in zip(nearby,nearby[1:])],default=0)<=5)
        second_coverage.append(dict(block=b,covered=ok))
    inputs=all(v.sha(n)==h for n,h in p['input_files'].items())
    stopped=v.read(ROOT/'node-monitor-closed.json')['stopped']
    requests=[v.read(x) for x in ROOT.glob('request-*.json')]
    result.update(node_placement_ok=bool(placement_ok),execution_observer_coverage=bool(coverage),no_cleanup_race_flags=bool(clean),exact_training_steps=bool(steps),
        input_manifest_ok=inputs,all_execute_resource_flags=flags,lifecycle=lifecycle,
        gpu27_pressure_rows=len(second),gpu27_uid_threads_peak=max(x['uid_counts']['visible_threads'] for x in second),gpu27_pressure_coverage=second_coverage,
        node_monitor_stopped=stopped,reserved_physical_cpus=40,active_worker_and_service_physical_cpus=32,
        request_finish_reasons=dict(collections.Counter(x.get('finish_reason','unknown') for x in requests)),
        boundary=p['boundary'])
    result['full_capacity_gate']=bool(result['full_capacity_gate'] and placement_ok and coverage and clean and steps and inputs and stopped and not any(flags.values()) and len(second_coverage)==2 and all(x['covered'] for x in second_coverage))
    with (ROOT/'audit-v1.json').open('x') as file:json.dump(result,file,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as file:
        w=csv.DictWriter(file,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:x for k,x in result.items() if k not in ('lifecycle','comparisons','output_shapes')}))

if __name__=='__main__':audit(sys.argv[1],sys.argv[2])
