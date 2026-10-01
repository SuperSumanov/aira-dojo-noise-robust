"""Outcome-blind terminal census. Does not create/replace all-closed.json."""
import argparse, hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/research/d7/spc/yzyang4/task-feedback-evidence-edit-20261002-v1')
PLAN='5ef4fa98529f70662cadf14e3f9a4ec4427c823d4a9fd723c9b6c25dd6806814'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def census():
    assert sha(ROOT/'plan.json')==PLAN
    plan=read(ROOT/'plan.json')
    for rel,h in plan['files'].items():assert sha(ROOT/rel)==h,rel
    job=read(ROOT/'launch.json')['job'];assert str(job)=='15213'
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    # A completed job can age out of squeue's ID lookup (nonzero exit).
    # Require a successful owner inventory, then absence of this exact job.
    queue=subprocess.check_output(['squeue','-u','yzyang4','-h','-o','%i|%T'],env=env,text=True,timeout=25)
    assert all(line.split('|')[0]!=str(job) for line in queue.splitlines()),'job still in queue'
    fields=['JobIDRaw','State','ExitCode','ElapsedRaw','AllocTRES','NodeList']
    raw=subprocess.check_output(['sacct','-j',str(job),'-n','-P','-o',','.join(fields)],env=env,text=True,timeout=25)
    records=[dict(zip(fields,line.split('|'))) for line in raw.splitlines() if line.strip()]
    indexed={r['JobIDRaw']:r for r in records};assert len(indexed)==len(records)
    terminal={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'}
    assert all(r['State'].split()[0] in terminal for r in records)
    assert indexed[str(job)]['State']=='FAILED'
    closed=read(ROOT/'closed.json');assert closed['service_closed'] is True
    assert not (ROOT/'all-closed.json').exists(),'unexpected original gate change'
    service=read(ROOT/'service-native.json');seen=set();rows=[];bindings={}
    for name in ('plan.json','launch.json','closed.json','service-native.json','controller-error.json'):
        bindings[name]=sha(ROOT/name)
    for s in plan['schedule']:
        ep=ROOT/f'episode-{s["index"]}';native=read(ep/'native.json')
        assert str(native['job'])==str(job) and native['index']==s['index']
        assert native['config_sha256']==sha(ROOT/f'configs/{s["index"]}.json')
        assert not set(native['gpu_uuids']) & set(service['gpu_uuids'])
        step=str(job)+'.'+str(native['step']);assert step not in seen;seen.add(step)
        assert indexed[step]['State'].split()[0] in terminal
        assert indexed[step]['NodeList']==indexed[str(job)]['NodeList']=='gpu28'
        names=('native.json','identity.json','launch.json','deadline.json','closed.json','finished.json','failure.json','completed.json')
        for name in names:
            if (ep/name).is_file():bindings[str((ep/name).relative_to(ROOT))]=sha(ep/name)
        artifacts=[]
        for pattern in ('action-*/result.json','action-*/submission.private.csv','action-*/node.private.json','action-*/generation.private.json','action-*/format.json','action-*/started.json','action-*/binding.json','action-*/selected.json'):
            artifacts.extend(ep.glob(pattern))
        for p in sorted(artifacts):bindings[str(p.relative_to(ROOT))]=sha(p)
        has_closed=(ep/'closed.json').exists()
        count=len(list(ep.glob('action-*/result.json')))
        if not has_closed:
            assert s['index']==10 and count==0 and not list(ep.glob('action-*/generation.private.json'))
            assert indexed[step]['State'].split()[0]=='CANCELLED'
        rows.append(dict(index=s['index'],step=step,state=indexed[step]['State'],elapsed_seconds=int(indexed[step]['ElapsedRaw']),original_closed=has_closed,returned_actions=count))
    assert len(rows)==12 and sum(x['original_closed'] for x in rows)==11
    elapsed=int(indexed[str(job)]['ElapsedRaw']);gpu_seconds=elapsed*5
    assert 'gres/gpu=5' in indexed[str(job)]['AllocTRES']
    return dict(schema='terminal-aborted-census-v1',utc=datetime.now(timezone.utc).isoformat(),
        status='ALL_PLANNED_STEPS_TERMINAL_ORIGINAL_BATCH_FAILED',job=str(job),plan_sha256=PLAN,
        original_primary_gate_passed=False,service_closed=True,queue_empty=True,records=records,episodes=rows,
        artifact_bindings=bindings,artifact_map_sha256=hashlib.sha256(json.dumps(bindings,sort_keys=True).encode()).hexdigest(),
        allocation_gpu_seconds=gpu_seconds,total_four_allocations_gpu_seconds=40919+gpu_seconds,
        total_four_allocations_gpu_hours=(40919+gpu_seconds)/3600,
        scope='lifecycle closure only; not completed experiment, image-cleanup attestation, performance verdict or missing-score imputation')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=census()
    with a.out.open('x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in out.items() if k!='artifact_bindings'},sort_keys=True))
