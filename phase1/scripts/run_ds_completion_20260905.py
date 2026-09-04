"""Bounded control-flow validation wrapper; no numerical training backend."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def run(output,commit):
    root=Path(__file__).resolve().parents[2]
    if output.exists() or not output.is_relative_to(Path('/tmp')) or not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('unsafe_output_or_commit')
    output.mkdir(mode=0o700)
    paths=['phase1/global_local_ds_completion.py','phase1/validate_ds_completion_source.py',
        'phase1/global_local_accelerate_update_adapter.py','phase1/global_local_execution_plan.py',
        'phase1/global_local_token_budget_plan.py','phase1/scripts/run_ds_completion_20260905.py',
        'phase1/DS_COMPLETION_PREFLIGHT_20260905.md']
    hashes={p:sha(root/p) for p in paths}
    context=dict(source_commit=commit,source_sha256=hashes,python=sys.version,
        started_at_utc=datetime.now(timezone.utc).isoformat(),child_timeout_seconds=120,
        legacy_commit='9e9ba2dae1e02b4167c0d65bf5eb0adbf1d79371')
    (output/'execution_context.json').write_text(json.dumps(context,sort_keys=True,indent=2)+'\n')
    env=dict(os.environ,PYTHONPATH=str(root),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',
        HF_HUB_OFFLINE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    records=[];failed=False
    for name in ('producer_a','producer_b'):
        command=[sys.executable,'-B','-m','phase1.validate_ds_completion_source']
        started=time.monotonic()
        try:
            p=subprocess.run(command,cwd=root,env=env,capture_output=True,timeout=120)
            stdout,stderr,rc=p.stdout,p.stderr,p.returncode
        except subprocess.TimeoutExpired as exc:stdout,stderr,rc=exc.stdout or b'',exc.stderr or b'',124
        (output/(name+'.json')).write_bytes(stdout)
        row=dict(name=name,source_commit=commit,command=json.dumps(command),seed=6,
            rc=rc,seconds=time.monotonic()-started,stderr_bytes=len(stderr),stderr_sha256=hashlib.sha256(stderr).hexdigest(),
            new_gpu_jobs=0,model_fits=0,api_calls=0)
        records.append(row);print(json.dumps(row),flush=True)
        if rc or stderr:failed=True;break
    with (output/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    if not failed:
        failed=((output/'producer_a.json').read_bytes()!=(output/'producer_b.json').read_bytes()
                or hashes!={p:sha(root/p) for p in paths})
    if not failed:
        result=json.loads((output/'producer_a.json').read_bytes())
        failed=(result['status']!='SOURCE_CONTROL_FLOW_VERIFIED_NOT_NUMERICAL_DEEPSPEED'
            or result['case_count']!=48 or result['legacy_false_success_detected_cases']!=24
            or len(result['injected_faults_detected'])!=3 or result['real_backend_executed'])
    (output/('FAILED' if failed else 'COMPLETE')).write_text(('FAILED' if failed else 'COMPLETE')+'\n')
    (output/'manifest.json').write_text(json.dumps({p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()},sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(status='FAILED_CLOSED' if failed else 'DS_COMPLETION_CONTROL_FLOW_COMPLETE',
        receipt_sha256=sha(output/'producer_a.json'))))
    return int(failed)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--source-commit',required=True)
    args=p.parse_args();raise SystemExit(run(args.output.absolute(),args.source_commit))
