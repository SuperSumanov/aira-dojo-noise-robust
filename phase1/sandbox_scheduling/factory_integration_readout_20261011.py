"""Independent fixed-six acceptance; no import of the experiment driver."""
import csv,json,os,re,statistics,subprocess,sys
from pathlib import Path
from verify_six_gpu_capacity import sha,read,output,difference

ROOT=Path('/research/d7/spc/yzyang4/resource-factory-integration-20261011-v1')
REFERENCE=Path('/research/d7/spc/yzyang4/resource-execution-guarded-six-20261011-v1/episode-0/output.private.csv')

def expected():return [(i,'normal' if i%2==0 else 'exit17',i//2) for i in range(6)]

def flags(text):
    return dict(http500=bool(re.search(r'\b500 DELETE /api/kernels/',text)),
        invalid_state='InvalidStateError' in text,sitecustomize='Error in sitecustomize' in text,
        forced_kill='did not terminate; sending SIGKILL' in text)

def audit(pin,job):
    assert sha(ROOT/'plan.json')==pin and read(ROOT/'launch.json')==dict(job=job,plan_sha256=pin)
    p=read(ROOT/'plan.json');assert [(r['index'],r['condition'],r['repeat']) for r in p['schedule']]==expected()
    assert p['planned']==6 and p['normal']==p['known_exit']==3 and p['candidate_seconds']==450
    assert p['source_seed']==42 and p['training_steps']==588 and p['numerical_tolerance']==1e-5
    source_ok=all(sha(ROOT/n)==h for n,h in p['files'].items())
    inputs_ok=all(sha(n)==h for n,h in p['input_files'].items())
    close=read(ROOT/'closed.json') if (ROOT/'closed.json').exists() else None
    rows=[];comparisons=[];valid=True
    for i,condition,repeat in expected():
        file=ROOT/f'results/row-{i}.json'
        actual=read(file) if file.exists() else {}
        row=dict(index=i,condition=condition,repeat=repeat,job=job,plan_sha256=pin,
            attempted=bool(actual),accepted=actual.get('accepted',False),error_type=actual.get('error_type'),
            execution_seconds=actual.get('execution_seconds'),exit_code=actual.get('exit_code'),
            timed_out=actual.get('timed_out'),training_steps=actual.get('training_steps'),output_sha256=actual.get('output_sha256'))
        if actual:
            assert (actual['index'],actual['condition'],actual['repeat'])==(i,condition,repeat)
            valid &= bool(actual.get('fresh_gateway_receipt')) and not any(actual.get('resource_flags',{'unknown':True}).values())
        if row['accepted']:
            if condition=='normal':
                t=read(ROOT/f'results/training-{i}.json');assert t['steps']==len(t['host_step_intervals'])==588
                assert all(x['devices']==['cuda:0'] and x['gradient_parameters']>0 for x in t['host_step_intervals'])
                out=ROOT/f'results/output-{i}.private.csv';assert sha(out)==row['output_sha256']
                assert sha(REFERENCE)==p['expected_output_sha256']
                delta=difference(out,REFERENCE)
                comparisons.append(dict(index=i,byte_equal=sha(out)==sha(REFERENCE),max_abs_diff=delta))
                valid &= row['exit_code']==0 and row['timed_out'] is False and delta<=1e-5
            else:
                assert read(ROOT/f"workspace/fault-start-{i}.json")==dict(exit_requested=17)
                valid &= bool(row['exit_code']!=0 and row['timed_out'] is False and row['execution_seconds']<20 and actual['lost_state'])
        rows.append(row)
    if close:
        assert close['planned']==6 and close['attempted']==sum(r['attempted'] for r in rows) and close['accepted']==sum(r['accepted'] for r in rows)
    log=(ROOT/'job.private.log').read_text(errors='replace') if (ROOT/'job.private.log').exists() else ''
    cleanup=flags(log)
    receipts=[read(f) for f in (ROOT/'workspace').glob('kernel-shutdown-guard-installed-*.json')]
    receipt_ok=len(receipts)==6 and all(x==dict(original_sha256='aaaee97aa5b9c52ae47c68f8503468153da8d2a6f0b8bd0756f55e5b14bb6c7e',transition_timeout=15,no_candidate_retry=True) for x in receipts)
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    raw=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    acc=[x.split('|') for x in raw.splitlines() if x.split('|')[0]==job];assert len(acc)==1
    state,sec,tres=acc[0][1:4];assert state not in ('RUNNING','PENDING','COMPLETING')
    assert re.search(r'(?:^|,)gres/gpu=1(?:,|$)',tres) and int(sec)<=900
    after=read(ROOT/'pressure-after.json') if (ROOT/'pressure-after.json').exists() else None
    tree_clean=bool(after and after['root_identity_stable'] and len(after['owned_descendants'])==1 and after['owned_descendants'][0]['pid']==after['root_pid'])
    times=[r['execution_seconds'] for r in rows if r['accepted'] and r['condition']=='exit17']
    result=dict(job=job,plan_sha256=pin,planned=6,attempted=sum(r['attempted'] for r in rows),accepted=sum(r['accepted'] for r in rows),
        unstarted=sum(not r['attempted'] for r in rows),manifest_ok=source_ok,input_manifest_ok=inputs_ok,scheduler_state=state,
        gpu_seconds=int(sec),gpu_seconds_cap=900,normal_comparisons= comparisons,cleanup_flags=cleanup,
        fresh_gateway_receipts=len(receipts),gateway_receipts_ok=receipt_ok,owned_descendants_clean=tree_clean,
        after_host_uid_counts=after['host_pressure']['uid_counts'] if after else None,
        known_exit_seconds=times,known_exit_median=statistics.median(times) if times else None,
        known_exit_sample_sd=statistics.stdev(times) if len(times)>1 else None,
        gate=bool(close and close['accepted']==6 and close['close_error'] is None and valid and source_ok and inputs_ok and receipt_ok and tree_clean and not any(cleanup.values()) and state=='COMPLETED'),
        boundary=p['boundary'])
    with (ROOT/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    with (ROOT/'audit-v1.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result))

if __name__=='__main__':audit(sys.argv[1],sys.argv[2])
