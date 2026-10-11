"""Pinned single-GPU diagnostic audit, all10 rows retained including failures."""
import csv,inspect,json,sys,time
from pathlib import Path
import verify_execution_six as v
from protocol_readout import ALLOWED
from stack_capture_evidence import stack_evidence,gpu_evidence

ROOT=Path('/research/d7/spc/yzyang4/resource-execution-stack-capture-20261011-v1')
PIN='4741e0748c51affd413700690d1f3f24e879c522f194b74e5226a63917ca27b8'
JOB='17566'

def adapted_verifier():
    source=inspect.getsource(v.verify)
    changes=[("root.name=='resource-execution-six-20261011-v1'",f'root.name=={ROOT.name!r}',1),
        ('expected=[(0,0,0,1),(1,1,0,1)]+[(2+(b-2)*6+s,b,s,6) for b in (2,3) for s in range(6)]','expected=[(i,i,0,1) for i in range(10)]',1),
        ("p['planned']==c['planned']==14","p['planned']==c['planned']==10",1),("p['gpus']==6","p['gpus']==1",1),
        ('range(4)','range(10)',2),('==6\n','==1\n',1),('cost=int(seconds)*6','cost=int(seconds)',1),
        ("p['gpu_seconds_cap']==10800","p['gpu_seconds_cap']==1800",1),('planned=14,attempted=','planned=10,attempted=',1),
        ('unstarted=14-','unstarted=10-',1),('gpu_seconds_cap=10800','gpu_seconds_cap=1800',1),
        ("c['complete']==14","c['complete']==10",1),('len(blocks)==4','len(blocks)==10',1),('len(pairs)==91','len(pairs)==45',1)]
    for a,b,n in changes:assert source.count(a)==n,(a,source.count(a));source=source.replace(a,b)
    scope=dict(v.__dict__);exec(compile(source,'same-verifier-ten-serial','exec'),scope)
    return scope['verify']

def audit():
    pins=v.read(ROOT/'readout-source.json')
    assert pins['readout_sha256']==v.sha(Path(__file__)) and pins['verifier_sha256']==v.sha(Path(v.__file__))
    assert pins['stack_evidence_sha256']==v.sha(Path(__file__).with_name('stack_capture_evidence.py'))
    rows,result=adapted_verifier()(ROOT,PIN,JOB)
    evidence=[]
    for row in rows:
        ep=ROOT/f"episode-{row['index']}";calls=v.read(ep/'protocol-calls.json') if (ep/'protocol-calls.json').exists() else None
        counters=v.read(ep/'gateway-counts.json') if (ep/'gateway-counts.json').exists() else None
        if counters is not None:assert all(ALLOWED.fullmatch(k) and type(x) is int and x>=0 for k,x in counters.items())
        if row['complete']:assert calls and len(calls)==5 and all(c['ready'] is True for c in calls)
        stacks=stack_evidence((ep/'kernel-stack.private.log').read_text(errors='replace')) if (ep/'kernel-stack.private.log').exists() else None
        gpu=None;call=v.read(ep/'execute-observation-1.json') if (ep/'execute-observation-1.json').exists() else None
        if call and (ep/'gpu-monitor.jsonl').exists():
            samples=[json.loads(x) for x in (ep/'gpu-monitor.jsonl').read_text().splitlines()];gpu=gpu_evidence(samples,call['start'],call['end'])
        evidence.append(dict(index=row['index'],attempted=row['attempted'],complete=row['complete'],protocol_calls=calls,gateway_counts=counters,stacks=stacks,gpu=gpu))
    result.update(evidence=evidence,boundary='Ten serial repeats maximum,first failure stops. Parent watchdog and gateway observers can change timing. Not six-way capacity, historical EAGAIN causal proof, new source/seed, speedup or quality.')
    with (ROOT/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:x for k,x in result.items() if k not in ('comparisons','evidence')}))
    print(json.dumps(dict(failures=[x for x in evidence if x['attempted'] and not x['complete']])))

def watch():
    end=time.monotonic()+1850;last=None
    while time.monotonic()<end:
        try:
            rows=[v.read(f) for f in sorted(ROOT.glob('episode-*/complete.json'))]
            state=dict(job=JOB,started=len(list(ROOT.glob('episode-*/candidate-start.json'))),
                terminals=[dict(index=x['index'],complete=x['complete'],error_type=x['error_type']) for x in rows],
                stack_files=len(list(ROOT.glob('episode-*/kernel-stack.private.log'))),closed=(ROOT/'closed.json').exists())
            if state!=last:print(json.dumps(state),flush=True);last=state
            if state['closed']:print(json.dumps(v.read(ROOT/'closed.json')),flush=True);break
        except (OSError,ValueError):pass
        time.sleep(15)

if __name__=='__main__':
    if sys.argv[1]=='selftest':adapted_verifier();print('verifier adaptation valid');sys.exit(0)
    assert v.sha(ROOT/'plan.json')==PIN
    if sys.argv[1]=='launch':
        with (ROOT/'launch.json').open('x') as f:json.dump(dict(job=JOB,plan_sha256=PIN),f)
        with (ROOT/'readout-source.json').open('x') as f:json.dump(dict(readout_sha256=v.sha(Path(__file__)),verifier_sha256=v.sha(Path(v.__file__)),stack_evidence_sha256=v.sha(Path(__file__).with_name('stack_capture_evidence.py'))),f)
        print('launch and readout pins recorded')
    elif sys.argv[1]=='watch':watch()
    elif sys.argv[1]=='audit':audit()
