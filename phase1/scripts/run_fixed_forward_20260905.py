"""Bounded exact-source A/B wrapper. Raw error payloads never leave this runner."""
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

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def run(output,commit):
    root=Path(__file__).resolve().parents[2]
    if output.exists() or not output.is_relative_to(Path('/tmp')) or not re.fullmatch('[0-9a-f]{40}',commit):
        raise ValueError('unsafe_output_or_commit')
    output.mkdir(mode=0o700)
    sources=['phase1/fixed_forward_rewire.py','phase1/historical_fixed_forward_readiness.py',
        'phase1/historical_label_reuse_support.py','phase1/global_local_execution_plan.py',
        'phase1/global_local_token_budget_plan.py','phase1/scripts/run_fixed_forward_20260905.py',
        'phase1/FIXED_FORWARD_REWIRE_PREFLIGHT_20260905.md']
    hashes={p:sha(root/p) for p in sources}
    env=dict(os.environ,PYTHONPATH=str(root),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',
        HF_HUB_OFFLINE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    context=dict(source_commit=commit,source_sha256=hashes,python=sys.version,
        started_at_utc=datetime.now(timezone.utc).isoformat(),child_timeout_seconds=300)
    (output/'execution_context.json').write_text(json.dumps(context,sort_keys=True,indent=2)+'\n')
    records=[]
    failed=False
    for name in ('producer_a','producer_b'):
        cmd=[sys.executable,'-B','-m','phase1.historical_fixed_forward_readiness']
        start=time.monotonic()
        try:
            proc=subprocess.run(cmd,cwd=root,env=env,capture_output=True,timeout=300)
            stdout,stderr,rc=proc.stdout,proc.stderr,proc.returncode
        except subprocess.TimeoutExpired as exc:stdout,stderr,rc=exc.stdout or b'',exc.stderr or b'',124
        (output/(name+'.json')).write_bytes(stdout)
        row=dict(name=name,source_commit=commit,command=json.dumps(cmd),rc=rc,
            seconds=time.monotonic()-start,stderr_bytes=len(stderr),stderr_sha256=hashlib.sha256(stderr).hexdigest(),
            new_gpu_jobs=0,model_fits=0,api_calls=0)
        records.append(row)
        print(json.dumps(row),flush=True)
        if rc or stderr:failed=True;break
    with (output/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    if not failed:
        failed=(output/'producer_a.json').read_bytes()!=(output/'producer_b.json').read_bytes() or hashes!={p:sha(root/p) for p in sources}
    if not failed:
        result=json.loads((output/'producer_a.json').read_bytes())
        failed=result['status']!='STRUCTURAL_ONLY_NOT_EFFECT' or len(result['results'])!=12 or result['pool_written']
    (output/('FAILED' if failed else 'COMPLETE')).write_text(('FAILED' if failed else 'COMPLETE')+'\n')
    manifest={p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()}
    (output/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(json.dumps(dict(status='FAILED_CLOSED' if failed else 'FIXED_FORWARD_CHAIN_COMPLETE',
        receipt_sha256=sha(output/'producer_a.json'))))
    return int(failed)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-commit',required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.output.absolute(),args.source_commit))
