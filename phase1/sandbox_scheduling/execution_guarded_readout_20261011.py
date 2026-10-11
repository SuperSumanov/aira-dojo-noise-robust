"""Original six-GPU capacity verifier plus actual lifecycle/cleanup evidence."""
import csv,inspect,json,re,sys,time
from pathlib import Path
import verify_execution_six as v
from execution_exit_readout_20261011 import events
from kernel_shutdown_guard import METHOD_SHA
ROOT=Path('/research/d7/spc/yzyang4/resource-execution-guarded-six-20261011-v1')
PIN='d96fba91f303325714b8a7320571776cbec66a87ccaa45f12d01afd5a2b418a5'
JOB='17570'
def verifier():
    source=inspect.getsource(v.verify);old="root.name=='resource-execution-six-20261011-v1'"
    assert source.count(old)==1
    scope=dict(v.__dict__);exec(compile(source.replace(old,f'root.name=={ROOT.name!r}'),'same-six-verifier-guarded-root','exec'),scope)
    return scope['verify']
def pins():return dict(readout_sha256=v.sha(Path(__file__)),verifier_sha256=v.sha(Path(v.__file__)),events_source_sha256=v.sha(Path(__file__).with_name('execution_exit_readout_20261011.py')))
def audit():
    assert v.read(ROOT/'readout-source.json')==pins()
    rows,result=verifier()(ROOT,PIN,JOB);evidence=[];coverage=True;clean=True
    for row in rows:
        ep=ROOT/f"episode-{row['index']}";ev=events(ep)
        installed=v.read(ep/'kernel-shutdown-guard-installed.json') if (ep/'kernel-shutdown-guard-installed.json').exists() else None
        if row['candidate_started']:
            coverage &= installed==dict(original_sha256=METHOD_SHA,transition_timeout=15,no_candidate_retry=True)
            coverage &= any(x['event']=='launched' for x in ev)
        call=v.read(ep/'execute-observation-1.json') if (ep/'execute-observation-1.json').exists() else None
        during=[x for x in ev if x['event']=='exit_observed' and call and call['start']<=x['time']<=call['end']]
        raw=(ep/'worker.private.log').read_text(errors='replace') if (ep/'worker.private.log').exists() else ''
        flags=dict(http500=bool(re.search(r'\b500 DELETE /api/kernels/',raw)),invalid_state='InvalidStateError' in raw,forced_server_kill='did not terminate; sending SIGKILL' in raw)
        clean &= not any(flags.values())
        evidence.append(dict(index=row['index'],attempted=row['attempted'],complete=row['complete'],events=ev,exits_during_candidate=during,call=call,cleanup_flags=flags))
    result.update(lifecycle=evidence,lifecycle_coverage=coverage,no_cleanup_race_flags=clean,execution_gate=bool(result['execution_gate'] and coverage and clean),
        boundary='One fixed source/seed/public synthetic fixture. Complete six-GPU gate only; not six tasks,co-resident model capacity,EAGAIN root cause,speedup or quality. No retries.')
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
            state=dict(job=JOB,started=len(list(ROOT.glob('episode-*/candidate-start.json'))),complete=sum(x['complete'] for x in rows),terminals=len(rows),closed=(ROOT/'closed.json').exists(),
                exits=[dict(index=i,**x) for i in range(14) for x in events(ROOT/f'episode-{i}') if x['event']=='exit_observed' and x['returncode']!=0])
            if state!=last:print(json.dumps(state),flush=True);last=state
            if state['closed']:print(json.dumps(v.read(ROOT/'closed.json')),flush=True);return
        except (OSError,ValueError):pass
        time.sleep(15)
if __name__=='__main__':
    assert v.sha(ROOT/'plan.json')==PIN
    if sys.argv[1]=='launch':
        with (ROOT/'launch.json').open('x') as f:json.dump(dict(job=JOB,plan_sha256=PIN),f)
        with (ROOT/'readout-source.json').open('x') as f:json.dump(pins(),f)
        print('launch and readout pinned')
    elif sys.argv[1]=='audit':audit()
    elif sys.argv[1]=='watch':watch()
