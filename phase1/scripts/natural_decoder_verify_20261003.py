"""Supplement verification; preserve frozen readout and expose dependency-null bug."""
import csv,hashlib,json,math,os,statistics,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/natural-decoder-factorial-20261003-v1');OLD=R.parent/'natural-opportunity-20261003-v1'
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,x):
    with p.open('x') as f:json.dump(x,f,indent=2,sort_keys=True,allow_nan=False)
def main():
    plan=read(R/'plan.json');summary=read(R/'readout.json');bindings=read(R/'readout-bindings.private.json')
    assert sha(R/'plan.json')==summary['plan_sha256'] and plan['pre_score']
    for rel,h in plan['files'].items():assert sha(R/rel)==h
    for path,h in bindings.items():assert sha(Path(path))==h
    labelpaths=[x for x in bindings if x.endswith('/private/dsearch.csv')];assert len(labelpaths)==1
    truth={r['textID']:set(r['selected_text'].lower().split()) for r in rows(Path(labelpaths[0]))}
    recomputed={}
    for path in bindings:
        if path in labelpaths or path.endswith('/test.csv'):continue
        pred={r['textID']:set(r['selected_text'].lower().split()) for r in rows(Path(path))};assert set(pred)==set(truth)
        value=math.fsum(len(truth[k]&pred[k])/len(truth[k]|pred[k]) for k in truth)/len(truth);recomputed[path]=value
    for row in summary['rows']:
        root=OLD if row['arm'] in ('original','mask_only') else R
        arm='modified' if row['arm']=='mask_only' else row['arm']
        s=next(s for s in read(root/'plan.json')['schedule'] if s['state']==5 and s['seed']==row['seed'] and s['arm']==arm)
        a=root/f'episode-{s["index"]}/action-0';r=read(a/'result.json')
        assert row['valid']==r['output_present']
        if row['valid']:assert math.isclose(row['score'],recomputed[str(a/'submission.private.csv')],abs_tol=1e-11)
        if row['neutral_score'] is not None:assert math.isclose(row['neutral_score'],recomputed[str(R/f'neutral-{row["seed"]}-{row["arm"]}.private.csv')],abs_tol=1e-11)
    corrected=[]
    for p in summary['pairs']:
        a,b,c,d=[p[n] for n in ('original','mask_only','axis_only','joint')]
        gain=d-a if a is not None and d is not None else None
        qualified=gain is not None and gain>=.01 and d-p['fulltext']>=.01
        corrected.append(dict(seed=p['seed'],joint_gain=gain,joint_minus_fulltext=d-p['fulltext'] if d is not None else None,
            full_factorial_interaction=d-b-c+a if all(x is not None for x in (a,b,c,d)) else None,qualified=qualified))
    assert all(p['qualified'] for p in corrected)==summary['qualified']
    corrections=[dict(seed=p['seed'],field='joint_gain',frozen_value=next(x for x in summary['pairs'] if x['seed']==p['seed'])['joint_gain'],corrected_value=p['joint_gain']) for p in corrected if p['joint_gain']!=next(x for x in summary['pairs'] if x['seed']==p['seed'])['joint_gain']]
    accounting=[];env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    for root in (OLD,R):
        job=read(root/'launch.json')['job'];text=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode'],env=env,text=True,timeout=25)
        fields=next(x for x in text.splitlines() if x.split('|')[0]==job).split('|');assert fields[1]=='COMPLETED' and fields[4]=='0:0' and 'gres/gpu=2' in fields[3]
        accounting.append(dict(job=job,elapsed_seconds=int(fields[2]),allocated_gpus=2,gpu_hours=int(fields[2])*2/3600))
    for s in plan['schedule']:
        ep=R/f'episode-{s["index"]}';n=read(ep/'native.json');b=read(ep/'action-0/binding.json')
        assert n['job']==read(R/'launch.json')['job'] and len(n['gpu_uuids'])==1 and n['config_sha256']==sha(R/'configs'/f'{s["index"]}.json')
        assert b['system_bindpaths_disabled'] and b['namespace']['exact_device_namespace']
        assert read(ep/'closed.json')['returncode']==0
    total=sum(x['gpu_hours'] for x in accounting);assert total<=3
    out=dict(status='PASS_WITH_REPORTED_READOUT_CORRECTION',plan_sha256=sha(R/'plan.json'),summary_sha256=sha(R/'readout.json'),
        verifier_sha256=sha(Path(__file__)),corrected_pairs=corrected,corrections=corrections,qualified=summary['qualified'],accounting=accounting,total_allocated_gpu_hours=total,
        reason='Frozen readout unnecessarily required all four factorial cells to print joint-original. Seed173 has that contrast despite missing mask-only. Original file preserved; qualification remains false.',
        limitation='No full 2x2 interaction is estimable at either seed. Missing/timeout is not zero. One natural source, no new method claim.')
    write(R/'verification.json',out);print(json.dumps(out))
if __name__=='__main__':main()
