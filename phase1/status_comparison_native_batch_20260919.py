"""Structure-only status of the fixed native batch-order allocation."""
import datetime,json,os,subprocess
from pathlib import Path
ROOT=Path('/research/d7/spc/yzyang4/comparison-native-batch-order-20260919-hz3c589n')
if not (ROOT/'launch.json').exists():
    print(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',cpu_complete=(ROOT/'batch-cpu.json').exists())))
else:
    job=json.loads((ROOT/'launch.json').read_bytes())['job']
    raw=subprocess.check_output(['sacct','-X','-j',job,'-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList,AllocTRES%128'],env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf'),text=True,timeout=25)
    allocation,=[line.split('|') for line in raw.splitlines() if line.split('|')[0]==job]
    out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job=job,allocation=allocation,services_ready=(ROOT/'services-ready.json').exists(),closed=(ROOT/'closed.json').exists(),episodes=[])
    for i in range(4):
        ep=ROOT/f'episode-{i}'
        start=json.loads((ep/'start.json').read_bytes()) if (ep/'start.json').exists() else None
        out['episodes'].append(dict(index=i,started=start is not None,start_utc=start['utc'] if start else None,finished=(ep/'finished.json').exists(),generation_files=len(list(ep.glob('generation-*.private.json'))),action_files=len(list(ep.glob('action-*.json')))))
    if out['closed']:out['closed_status']=json.loads((ROOT/'closed.json').read_bytes())['status']
    print(json.dumps(out))
