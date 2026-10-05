"""Fixed development run structural status; never emit predictions/model replies."""
import collections,json,os,subprocess
from pathlib import Path
R=Path('/research/d7/spc/yzyang4/implementation-reset-20261005-v2')
def read(p):return json.loads(p.read_bytes())
report={'prepared':(R/'plan.json').exists(),'submitted':(R/'launch.json').exists(),
        'service_ready':(R/'service-ready.json').exists(),'closed':(R/'closed.json').exists()}
if (R/'service.private.log').exists():
    p=R/'service.private.log'
    with p.open('rb') as f:
        f.seek(max(0,p.stat().st_size-32768));tail=f.read().decode(errors='replace')
    report['service_log_bytes']=p.stat().st_size
    report['service_flags']={x:(x in tail) for x in ['Loading safetensors','Loading model weights','Application startup complete','CUDA out of memory','Permission denied','Traceback','POLICY9B_SERVICE_CUDA']}
if report['submitted']:
    job=read(R/'launch.json')['job'];report['job']=job
    env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    report['queue']=subprocess.check_output(['squeue','-j',job,'-h','-o','%i %T %M %R'],env=env,text=True,timeout=15).strip()
if (R/'source-gate.json').exists():report['source_gate_passed']=read(R/'source-gate.json')['passed']
report['episodes']=[]
for i in range(18):
    ep=R/f'episode-{i}'
    if not (ep/'launch.json').exists():continue
    row={'index':i,'closed':(ep/'closed.json').exists(),
         'returned_generations':len(list(ep.glob('action-*/generation.private.json'))),
         'execution_results':len(list(ep.glob('action-*/result.json'))),
         'contract_rejections':len(list(ep.glob('action-*/contract-rejection.json')))}
    reasons=collections.Counter()
    for p in ep.glob('action-*/contract-rejection.json'):
        reasons.update(read(p)['screen']['reasons'])
    if reasons:row['rejection_reasons']=dict(reasons)
    for file,key in [('finished.json','status'),('failure.json','error_type')]:
        if (ep/file).exists():row[key]=read(ep/file).get(key)
    report['episodes'].append(row)
if (R/'controller-error.json').exists():report['controller_error']=read(R/'controller-error.json')['error_type']
print(json.dumps(report))
