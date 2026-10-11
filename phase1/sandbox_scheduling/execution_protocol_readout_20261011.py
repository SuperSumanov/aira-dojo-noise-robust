"""Independent original14 denominator plus enum-only protocol evidence."""
import csv,inspect,json,sys,time
from pathlib import Path
import verify_execution_six as v
from protocol_readout import ALLOWED

ROOT=Path('/research/d7/spc/yzyang4/resource-execution-protocol-six-20261011-v1')
PIN='ee8e9295ba7cce669d7cd4d9d870b9d05b66bd597540632ab5dee3049944670f'
JOB='17565'

def existing_verify():
    source=inspect.getsource(v.verify)
    old="root.name=='resource-execution-six-20261011-v1'"
    assert source.count(old)==1
    scope=dict(v.__dict__)
    exec(compile(source.replace(old,f'root.name=={ROOT.name!r}'),'same-capacity-verifier-new-root','exec'),scope)
    return scope['verify']

def audit():
    rows,result=existing_verify()(ROOT,PIN,JOB)
    protocol=[]
    for row in rows:
        ep=ROOT/f"episode-{row['index']}"
        calls=v.read(ep/'protocol-calls.json') if (ep/'protocol-calls.json').exists() else None
        counters=v.read(ep/'gateway-counts.json') if (ep/'gateway-counts.json').exists() else None
        if counters is not None:assert all(ALLOWED.fullmatch(k) and type(x) is int and x>=0 for k,x in counters.items())
        if row['complete']:assert calls and len(calls)==5 and all(c['ready'] is True for c in calls)
        protocol.append(dict(index=row['index'],attempted=row['attempted'],complete=row['complete'],calls=calls,gateway_counts=counters))
    observed=all(x['gateway_counts'] and x['gateway_counts'].get('incoming_forwarded',0)>0 for x in protocol if x['complete'])
    result.update(protocol=protocol,completed_protocol_observed=bool(observed),execution_gate=result['execution_gate'] and observed,
        boundary='Original CLI with observer imports may perturb timing. Same source/seed and no model service; not root-cause repair,2+6 capacity,speedup or quality.')
    with (ROOT/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:x for k,x in result.items() if k not in ('comparisons','protocol')}))
    print(json.dumps(dict(failures=[x for x in protocol if x['attempted'] and not x['complete']])))

def watch():
    last=None;end=time.monotonic()+1850
    while time.monotonic()<end:
        try:
            rows=[v.read(f) for f in sorted(ROOT.glob('episode-*/complete.json'))]
            init=[v.read(f) for f in sorted(ROOT.glob('episode-*/cuda-before.json'))]
            state=dict(job=JOB,host_cuda_codes=[r.get('cuinit_rc') for r in init],
                candidates_started=len(list(ROOT.glob('episode-*/candidate-start.json'))),
                terminals=[dict(index=r['index'],complete=r['complete'],error_type=r['error_type']) for r in rows],closed=(ROOT/'closed.json').exists())
            if state!=last:print(json.dumps(state),flush=True);last=state
            if state['closed']:print(json.dumps(v.read(ROOT/'closed.json')),flush=True);break
        except (OSError,ValueError):pass
        time.sleep(15)

if __name__=='__main__':
    assert v.sha(ROOT/'plan.json')==PIN
    if sys.argv[1]=='launch':
        with (ROOT/'launch.json').open('x') as f:json.dump(dict(job=JOB,plan_sha256=PIN),f)
        with (ROOT/'readout-source.json').open('x') as f:json.dump(dict(readout_sha256=v.sha(Path(__file__)),verifier_sha256=v.sha(Path(v.__file__))),f)
        print('launch and readout pins recorded')
    elif sys.argv[1]=='watch':watch()
    elif sys.argv[1]=='audit':audit()
