"""Pinned full-denominator readout; native exit events are not EAGAIN proof."""
import csv,json,sys,time
from pathlib import Path
import stack_capture_readout_20261011 as prior
from kernel_lifecycle_observer import POLL_SHA,LAUNCH_SHA

v=prior.v
ROOT=Path('/research/d7/spc/yzyang4/resource-execution-exit-capture-20261011-v1')
PIN='64d4d03d1b4513bfac11518736671031691f334334195e134eab564ba99931f0'
JOB='17567'
prior.ROOT=ROOT

def events(ep):
    path=ep/'kernel-lifecycle.jsonl'
    if not path.exists():return []
    rows=[]
    for line in path.read_text().splitlines():
        row=json.loads(line)
        assert row['event'] in ('launched','exit_observed')
        assert set(row)==({'event','pid','time'} if row['event']=='launched' else {'event','pid','time','returncode'})
        assert type(row['pid']) is int and row['pid']>0
        if row['event']=='exit_observed':assert type(row['returncode']) is int
        rows.append(row)
    return rows

def pins():
    return dict(readout_sha256=v.sha(Path(__file__)),verifier_sha256=v.sha(Path(v.__file__)),
        adaptation_sha256=v.sha(Path(prior.__file__)),observer_sha256=v.sha(Path(__file__).with_name('kernel_lifecycle_observer.py')))

def audit():
    assert v.read(ROOT/'readout-source.json')==pins()
    rows,result=prior.adapted_verifier()(ROOT,PIN,JOB);evidence=[]
    for row in rows:
        ep=ROOT/f"episode-{row['index']}";ev=events(ep)
        installed=v.read(ep/'kernel-lifecycle-installed.json') if (ep/'kernel-lifecycle-installed.json').exists() else None
        if row['candidate_started']:
            assert installed==dict(poll_sha256=POLL_SHA,launch_sha256=LAUNCH_SHA,no_retry=True,no_signals=True)
            assert any(x['event']=='launched' for x in ev)
        call=v.read(ep/'execute-observation-1.json') if (ep/'execute-observation-1.json').exists() else None
        during=[x for x in ev if x['event']=='exit_observed' and call and call['start']<=x['time']<=call['end']]
        evidence.append(dict(index=row['index'],attempted=row['attempted'],complete=row['complete'],events=ev,
            exits_during_candidate=during,call=call))
    result.update(lifecycle=evidence,boundary='Original source/seed/image10serial maximum,first failure stops;no watchdog. Provisioner instrumentation may affect timing. Native exit is not the historical OpenBLAS root cause or6-way capacity/quality.')
    with (ROOT/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:x for k,x in result.items() if k not in ('comparisons','lifecycle')}))
    print(json.dumps(dict(failures=[x for x in evidence if x['attempted'] and not x['complete']])))

def watch():
    last=None;end=time.monotonic()+1850
    while time.monotonic()<end:
        try:
            rows=[v.read(f) for f in ROOT.glob('episode-*/complete.json')]
            state=dict(job=JOB,started=len(list(ROOT.glob('episode-*/candidate-start.json'))),complete=sum(x['complete'] for x in rows),
                terminals=len(rows),closed=(ROOT/'closed.json').exists(),
                exits=[dict(index=i,**e) for i in range(10) for e in events(ROOT/f'episode-{i}') if e['event']=='exit_observed' and e['returncode']!=0])
            if state!=last:print(json.dumps(state),flush=True);last=state
            if state['closed']:print(json.dumps(v.read(ROOT/'closed.json')),flush=True);return
        except (OSError,ValueError):pass
        time.sleep(15)

if __name__=='__main__':
    if sys.argv[1]=='selftest':prior.adapted_verifier();print('ten-serial verifier adaptation valid');sys.exit(0)
    assert v.sha(ROOT/'plan.json')==PIN
    if sys.argv[1]=='launch':
        with (ROOT/'launch.json').open('x') as f:json.dump(dict(job=JOB,plan_sha256=PIN),f)
        with (ROOT/'readout-source.json').open('x') as f:json.dump(pins(),f)
        print('launch and readout pins recorded')
    elif sys.argv[1]=='watch':watch()
    elif sys.argv[1]=='audit':audit()
