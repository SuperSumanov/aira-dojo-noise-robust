"""Independent 2+4 capacity readout: frozen denominator, no quality claims."""
import csv,inspect,json,os,re,subprocess,sys,time
from pathlib import Path
import verify_six_gpu_capacity as v
from execution_exit_readout_20261011 import events
from kernel_shutdown_guard import METHOD_SHA

ROOT=Path('/research/d7/spc/yzyang4/resource-joint-four-capacity-20261011-v1')
FLAGS=('resource temporarily unavailable','pthread_create',"can't start new thread",'out of memory')

def adapt(source):
    changes=(
        ('2+(b-2)*6+s,b,s,(s+b)%2,6','2+(b-2)*4+s,b,s,(s+b)%2,4'),
        ('for s in range(6)','for s in range(4)'),
        ("p['planned'] == close['planned'] == 14 and p['gpus'] == 8","p['planned'] == close['planned'] == 10 and p['gpus'] == 6"),
        ('assert gpus==8','assert gpus==6'),
        ('planned=14,attempted=','planned=10,attempted='),
        ("unstarted=14-close['attempted']","unstarted=10-close['attempted']"),
        ("close['complete']==close['requests_complete']==14","close['complete']==close['requests_complete']==10"),
        ("summary['cuda_gradient_receipts']==14","summary['cuda_gradient_receipts']==10"),
        ('len(comparisons)==42','len(comparisons)==20'))
    for before,after in changes:
        assert source.count(before)==1,(before,source.count(before))
        source=source.replace(before,after)
    return source

def base_verify(root,pin,job):
    scope=dict(v.__dict__)
    exec(compile(adapt(inspect.getsource(v.verify)),'independent-two-plus-four-readout','exec'),scope)
    return scope['verify'](root,pin,job)

def pins():
    return {n:v.sha(Path(__file__).with_name(n)) for n in
        (Path(__file__).name,'verify_six_gpu_capacity.py','execution_exit_readout_20261011.py','kernel_shutdown_guard.py')}

def extra_gate(rows,result,coverage,clean,flags,inputs,steps):
    return bool(result['full_capacity_gate'] and coverage and clean and not any(flags.values()) and inputs and steps
        and len(rows)==10 and sum(x['complete'] for x in rows)==10
        and [(x['gpus'],x['physical_cores']) for x in result['blocks']]==[(3,12),(3,12),(6,24),(6,24)])

def audit(pin,job):
    assert v.read(ROOT/'readout-source.json')==pins()
    assert v.sha(ROOT/'plan.json')==pin and v.read(ROOT/'launch.json')==dict(job=job,plan_sha256=pin)
    if not (ROOT/'closed.json').exists():
        # No invented controller receipt; retain the full planned denominator.
        assert (ROOT/'allocation-closed.json').exists()
        assert not list(ROOT.glob('episode-*/complete.json')), 'partial worker evidence requires explicit reconciliation'
        env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
        raw=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
        account=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==job];assert len(account)==1
        state,seconds,tres=account[0][1:4];assert state not in ('RUNNING','PENDING','COMPLETING')
        gpus=int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1]);assert gpus==6
        result=dict(job=job,plan_sha256=pin,planned=10,attempted=0,complete=0,unstarted=10,
            controller_receipt_missing=True,allocation=v.read(ROOT/'allocation-closed.json'),scheduler_state=state,
            gpu_seconds=int(seconds)*gpus,gpu_seconds_cap=14400,full_capacity_gate=False)
        assert result['gpu_seconds']<=14400
        rows=[dict(**r,job=job,plan_sha256=pin,attempted=False,complete=False) for r in v.read(ROOT/'plan.json')['schedule']]
    else:
        rows,result=base_verify(ROOT,pin,job);p=v.read(ROOT/'plan.json')
        inputs=all(v.sha(n)==h for n,h in p['input_files'].items())
        flags={k:0 for k in FLAGS};coverage=True;clean=True;steps=True;evidence=[]
        for row in rows:
            ep=ROOT/f"episode-{row['index']}";ev=events(ep)
            observations=[v.read(f) for f in ep.glob('execute-observation-*.json')]
            for call in observations:
                assert set(call['flags'])==set(flags)
                for k in flags:flags[k]+=bool(call['flags'][k])
            if row['complete']:
                coverage &= len(observations)==3 and {x['call'] for x in observations}=={0,1,2}
                steps &= row['gpu_steps']==(150 if row['program']==0 else 588)
            if row['candidate_started']:
                installed=v.read(ep/'kernel-shutdown-guard-installed.json') if (ep/'kernel-shutdown-guard-installed.json').exists() else None
                coverage &= installed==dict(original_sha256=METHOD_SHA,transition_timeout=15,no_candidate_retry=True)
                coverage &= any(x['event']=='launched' for x in ev)
            raw=(ep/'worker.private.log').read_text(errors='replace') if (ep/'worker.private.log').exists() else ''
            cleanup=dict(http500=bool(re.search(r'\b500 DELETE /api/kernels/',raw)),invalid_state='InvalidStateError' in raw,
                forced_server_kill='did not terminate; sending SIGKILL' in raw)
            clean &= not any(cleanup.values())
            candidate=next((x for x in observations if x['call']==1),None)
            exits=[x for x in ev if x['event']=='exit_observed' and candidate and candidate['start']<=x['time']<=candidate['end']]
            evidence.append(dict(index=row['index'],events=ev,exits_during_candidate=exits,cleanup_flags=cleanup,execute_calls=len(observations)))
        gate=extra_gate(rows,result,coverage,clean,flags,inputs,steps)
        result.update(full_capacity_gate=gate,execution_observer_coverage=bool(coverage),no_cleanup_race_flags=bool(clean),
            exact_training_steps=bool(steps),input_manifest_ok=inputs,all_execute_resource_flags=flags,lifecycle=evidence)
    result['boundary']='2local serving+4task GPUs,2fixed public-fixture programs/seed42. Not2+6,production failure-rate proof,EAGAIN root cause,newtasks,agent quality or speedup.'
    with (ROOT/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({k:x for k,x in result.items() if k not in ('comparisons','lifecycle','output_shapes')}))

def watch():
    last=None;deadline=time.monotonic()+2450
    while time.monotonic()<deadline:
        terminal=[v.read(f) for f in ROOT.glob('episode-*/complete.json')]
        state=dict(service_ready=(ROOT/'service-ready.json').exists(),started=len(list(ROOT.glob('episode-*/candidate-start.json'))),
            complete=sum(x['complete'] for x in terminal),terminals=len(terminal),allocation_closed=(ROOT/'allocation-closed.json').exists())
        if state!=last:print(json.dumps(state),flush=True);last=state
        if state['allocation_closed']:return
        time.sleep(15)

if __name__=='__main__':
    os.umask(0o077);mode=sys.argv[1]
    if mode=='selftest':adapt(inspect.getsource(v.verify));print('readout adaptation valid')
    elif mode=='pin':
        assert not (ROOT/'launch.json').exists()
        with (ROOT/'readout-source.json').open('x') as f:json.dump(pins(),f)
        print('readout pinned before submission')
    elif mode=='audit':audit(sys.argv[2],sys.argv[3])
    elif mode=='watch':watch()
    else:raise ValueError(mode)
