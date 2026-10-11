"""Independent fixed-matrix readout. A completed probe is not a healthy GPU."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def summarize(rows):
    labels={};uuids={};passed={}
    for mode in ('host','image'):
        for mask in ('default','unset'):
            name=mode+'-'+mask
            chosen=[r for r in rows if r['mode']==mode and r['mask']==mask]
            labels[name]=dict(Counter(str(r.get('probe',{}).get('cuinit_rc','missing')) for r in chosen))
            uuids[name]=[r.get('probe',{}).get('uuids',[]) for r in chosen]
            passed[name]=sum(r.get('returncode')==0 and r.get('probe',{}).get('cuinit_rc')==0
                and r.get('probe',{}).get('visible_devices')==1 and 'error_type' not in r.get('probe',{})
                and (mode=='host' or r.get('probe',{}).get('arithmetic_pass') is True) for r in chosen)
    unique={k:len({x[0] for x in v if len(x)==1}) for k,v in uuids.items()}
    return dict(cuinit_status_counts=labels,single_device_pass_counts=passed,unique_single_device_uuids=unique)

def main(root,pin,job):
    assert root.parent==Path('/research/d7/spc/yzyang4') and re.fullmatch('[a-f0-9]{64}',pin) and job.isdigit()
    assert sha(root/'plan.json')==pin
    p=read(root/'plan.json');assert all(sha(root/n)==h for n,h in p['files'].items())
    c=read(root/'closed.json');rows=[];identities=[];seen=set();disjoint=True
    for index in range(8):
        ep=root/f'slot-{index}'
        if not(ep/'complete.json').exists():continue
        item=read(ep/'complete.json');ident=read(ep/'identity.json')
        assert item['index']==index and ident['job']==job and item['observed']==len(item['rows'])==4
        assert {(r['mode'],r['mask']) for r in item['rows']}=={(a,b) for a in ('host','image') for b in ('default','unset')}
        physical={tuple(x) for x in ident['physical_cores']};disjoint &= len(physical)==4 and not bool(physical & seen);seen|=physical
        rows+=item['rows'];identities.append(ident)
    assert len(rows)==c['observed_subprobes'] and len(identities)==c['observed_slots']
    assert c['planned_slots']==8 and c['expected_subprobes']==32
    assert sorted(c['rows'],key=lambda x:x['index'])==[read(root/f'slot-{i}/complete.json') for i in range(8) if (root/f'slot-{i}/complete.json').exists()]
    summary=summarize(rows)
    aligned=[]
    for item in c['rows']:
        data={(r['mode'],r['mask']):r.get('probe',{}) for r in item['rows']}
        aligned.append(data[('host','default')].get('uuids')==data[('image','default')].get('uuids')
            and len(data[('host','default')].get('uuids',[]))==1)
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    acc=subprocess.check_output(['sacct','-X','-j',job,'-n','-P','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    a=[x.split('|') for x in acc.splitlines() if x.split('|')[0]==job];assert len(a)==1
    state,seconds,tres=a[0][1:4];assert state not in ('RUNNING','PENDING','COMPLETING')
    assert int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',tres)[1])==8
    cost=int(seconds)*8;assert cost<=p['gpu_seconds_cap']==4800
    result=dict(job=job,plan_sha256=pin,closed_sha256=sha(root/'closed.json'),planned_slots=8,observed_slots=len(identities),
        expected_subprobes=32,observed_subprobes=len(rows),physical_cores=len(seen),cpu_sets_disjoint=bool(disjoint),
        default_host_image_aligned=bool(len(aligned)==8 and all(aligned)),**summary,
        default_device_gate=bool(state=='COMPLETED' and c['error_type'] is None and c['returncodes']==[0]*8
            and len(rows)==32 and disjoint and len(seen)==32 and all(aligned)
            and all(summary['single_device_pass_counts'][k]==summary['unique_single_device_uuids'][k]==8 for k in ('host-default','image-default'))),
        rows=c['rows'],identities=identities,gpu_seconds=cost,gpu_seconds_cap=4800,scheduler_state=state,
        boundary='Only eight owned-GPU initialization/arithmetic diagnostics. No model, task, capacity, speedup, quality or historical EAGAIN causal claim.')
    with (root/'audit-v1.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','identities')}))

if __name__=='__main__':main(Path(sys.argv[1]),sys.argv[2],sys.argv[3])
