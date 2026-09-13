"""Operational state only for the fixed EScope and zero-API classic searches."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import os
import subprocess
import monitor_edit_scope_20260914 as es

CLASSIC=Path('/research/d7/spc/yzyang4/forets-classic-control-20260914-6jkjkwd5')
with redirect_stdout(io.StringIO()) as capture:es.run()
state=json.loads(capture.getvalue());runs=[];reasons=[]
for block in (1,2):
    start=es.ROOT/f'block-{block}.runtime/started.json'
    if not start.exists():continue
    pool=es.read(es.ROOT/es.read(start)['pool_manifest'])
    for rid,t in pool['tasks'].items():
        if t['status'] in ('pending','launching','running') or not t['attempts']:continue
        identity=Path(t['attempts'][0]['identity_path'])
        if not identity.resolve().is_relative_to(es.ROOT/'runs/srun_pool'):raise ValueError('identity scope')
        execution=identity.with_suffix('.bounded')/'execution';p=execution/'summary.json'
        if not p.exists():continue
        summary=es.read(p);reason=summary['status']
        if reason=='failed':
            error=execution/'stderr.private.log'
            with error.open('rb') as f:f.seek(max(0,error.stat().st_size-4096));tail=f.read()
            if tail.rstrip().endswith(b'SearchBudgetExpired: insufficient search time for a bounded API request'):
                reason='api_admission_budget_expired'
        reasons.append(dict(run_id=rid,termination_reason=reason,elapsed_seconds=summary['elapsed_seconds']))
state['closed_termination_reasons']=reasons
for i in range(8):
    work=CLASSIC/f'work-{i}';result=CLASSIC/f'result-{i}.json'
    r=json.loads(result.read_bytes()) if result.exists() else {}
    runs.append(dict(index=i,status=r.get('status','running' if work.exists() else 'pending'),
        closed_attempt_files=len(list((work/'classic-trials').glob('*/attempt.json'))) if work.exists() else 0))
state['classic']=dict(job='13284',runs=runs,closure=(CLASSIC/'execution-finished.json').exists())
env=dict(os.environ,SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
state['all_queue']=subprocess.check_output(['squeue','-j','13282,13283,13284','-h','-o','%i|%T|%M|%N'],env=env,text=True,timeout=25).strip().splitlines()
state['all_accounting']=subprocess.check_output(['sacct','-X','-j','13282,13283,13284','-nP','-o','JobIDRaw,State%32,ElapsedRaw,NodeList'],env=env,text=True,timeout=25).strip().splitlines()
print(json.dumps(state))
