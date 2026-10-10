"""Read-only input audit; export only fixed structural fields, no raw logs."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, plan_sha, job):
    assert digest(root/'plan.json') == plan_sha
    plan=json.loads((root/'plan.json').read_text())
    close=json.loads((root/'closed.json').read_text())
    launch=json.loads((root/'launch.json').read_text())
    assert launch['job']==job and launch['plan_sha256']==plan_sha
    manifest_ok=all(digest(root/n)==h for n,h in plan['files'].items())
    rows=[]
    categories=('pthread_create failed','resource temporarily unavailable',"can't start new thread",'cannot allocate memory')
    error_counts={c:0 for c in categories}
    for item in plan['schedule']:
        block,index=item['block'],item['index']
        ep=root/f'block-{block}-worker-{index}'
        row=dict(**item,job=job,plan_sha256=plan_sha,source_commit=plan['source_commit'],
                 attempted=False,complete=False,seed=101101,returncode=None,error_type=None,
                 elapsed_seconds=None,kernel_check=False,numpy_version=None,torch_version=None)
        if (ep/'terminal.json').exists():
            t=json.loads((ep/'terminal.json').read_text())
            row.update(attempted=True,returncode=t['returncode'])
            if (ep/'complete.json').exists():
                c=json.loads((ep/'complete.json').read_text())
                row.update(complete=c['complete'],error_type=c['error_type'],elapsed_seconds=c['end']-c['start'])
            if (ep/'kernel.json').exists():
                k=json.loads((ep/'kernel.json').read_text())
                row.update(kernel_check=k['check'],numpy_version=k['numpy'],torch_version=k['torch'])
            if (ep/'worker.private.log').exists():
                raw=(ep/'worker.private.log').read_text(errors='replace').lower()
                for pattern in categories: error_counts[pattern]+=raw.count(pattern)
        rows.append(row)
    assert len(rows)==close['planned']==14
    assert sum(r['attempted'] for r in rows)==close['attempted']
    assert sum(r['complete'] for r in rows)==close['complete']
    assert all(r['returncode']==0 and r['kernel_check'] for r in rows if r['complete'])
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    account=subprocess.check_output(['sacct','-j',job,'-n','-P','-X','-o','JobID,State,ElapsedRaw,AllocTRES'],env=env,text=True)
    lines=[v.split('|') for v in account.strip().splitlines() if v.split('|')[0]==job]
    assert len(lines)==1 and lines[0][1] not in ('RUNNING','PENDING','COMPLETING')
    gpus=int(re.search(r'(?:^|,)gres/gpu=(\d+)(?:,|$)',lines[0][3])[1])
    seconds=int(lines[0][2]);assert gpus==plan['gpus']
    result=dict(job=job,plan_sha256=plan_sha,closed_sha256=digest(root/'closed.json'),
        manifest_ok=manifest_ok,planned=14,attempted=close['attempted'],complete=close['complete'],
        unstarted=14-close['attempted'],error_marker_counts=error_counts,scheduler_state=lines[0][1],
        gpu_seconds=gpus*seconds,cap_gpu_seconds=plan['gpu_seconds_cap'],
        full_matrix_pass=manifest_ok and close['complete']==14 and not any(error_counts.values()),
        qualification='Only fixed CPU kernels and container lifecycle; not MLE GPU execution or quality.')
    assert result['gpu_seconds']<=result['cap_gpu_seconds']
    return rows,result


if __name__=='__main__':
    root=Path(sys.argv[1]);pin=sys.argv[2];job=sys.argv[3]
    assert root.parent==Path('/research/d7/spc/yzyang4') and root.name.startswith('resource-')
    assert re.fullmatch('[a-f0-9]{64}',pin) and job.isdigit()
    rows,result=verify(root,pin,job)
    with (root/'audit-v1.csv').open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    with (root/'audit-v1.json').open('x') as f:json.dump(result,f,sort_keys=True,indent=2)
    print(json.dumps(result))
