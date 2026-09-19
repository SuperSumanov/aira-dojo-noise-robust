"""Closed failure-state reproduction only; no private labels or candidate grades."""
import json,os,re,subprocess
from pathlib import Path
from audit_comparison_third_prefix_20260919 import core
from run_comparison_pizza_prefix_20260919 import prepared,old
ROOT=old.BASE/'comparison-pizza-prefix-20260919-0guhqznb'
p=prepared(ROOT);job=old.read(ROOT/'launch.json')['job']
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=env,text=True,timeout=25)
a,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
if a[1].split()[0].rstrip('+') not in {'COMPLETED','FAILED','CANCELLED','TIMEOUT','NODE_FAIL','OUT_OF_MEMORY'}:raise ValueError('not closed')
if a[3]!='gpu28' or dict(x.split('=',1) for x in a[4].split(','))['gres/gpu']!='2':raise ValueError('resource identity')
rows=[];devices=[]
for original in p['rows']:
    index=original['index'];row={k:original[k] for k in ('index','seed','run','task','node','raw_code_sha256','code_sha256')}
    row.update(prefix_reproduced=None,status='unknown')
    if (ROOT/f'result-{index}.json').exists():
        result=old.read(ROOT/f'result-{index}.json')
        if any(result[k]!=v for k,v in original.items()):raise ValueError('source identity')
        row.update(status=result['status'],wall_seconds=result['wall_seconds'])
        if result['status']=='returned':
            binding=old.read(ROOT/f'identity-{index}.native-binding.json',result['native_binding_sha256'])
            if binding['native_identity']['job']!=job or binding['namespace']['exact_device_namespace'] is not True:raise ValueError('GPU isolation')
            devices.append(binding['native_identity']['selected_uuid'])
            log=ROOT/f'output-{index}.private.log';text=log.read_text()
            if old.SECRET.search(text.encode()):raise ValueError('output security')
            equal=False
            if result['exit_code']==1 and not result['timed_out']:
                try:equal=core(text)==original['historical_error']
                except ValueError:pass
            row.update(prefix_reproduced=equal,exit_code=result['exit_code'],timed_out=result['timed_out'],log_sha256=old.sha(log.read_bytes()))
    rows.append(row)
if len(devices)!=len(set(devices)):raise ValueError('worker device overlap')
result=dict(role='cross_task_prefix_state_reproduction_not_effect',job=job,commit=p['commit'],reader_sha256=old.sha(Path(__file__).read_bytes()),
    prepared_sha256=old.sha((ROOT/'prepared.json').read_bytes()),allocation_state=a[1],allocation_seconds=int(a[2]),gpu_hours=int(a[2])*2/3600,
    rows=rows,all_reproduced=all(r['prefix_reproduced'] is True for r in rows),labels_read=False,cached_outcomes_read=False)
old.write(ROOT/'summary.json',result);print(json.dumps(result,indent=2))
