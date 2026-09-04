"""Bounded parent runner; records failures, A/B bytes and exact source provenance."""
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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output, source_commit):
    root = Path(__file__).resolve().parents[2]
    if output.exists() or not output.is_relative_to(Path('/tmp')) or not re.fullmatch('[0-9a-f]{40}', source_commit):
        raise ValueError('unsafe_output_or_source_commit')
    output.mkdir(mode=0o700)
    source_paths = [
        'phase1/historical_reuse_execution_readiness.py', 'phase1/historical_label_reuse_support.py',
        'phase1/global_local_execution_plan.py', 'phase1/global_local_token_budget_plan.py',
        'phase1/verify_global_local_token_budget_plan.py',
        'phase1/scripts/run_historical_reuse_execution_20260904.py',
    ]
    source_hashes = {p: sha(root/p) for p in source_paths}
    env = dict(os.environ, CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONPATH=str(root))
    context = dict(source_commit=source_commit, source_sha256=source_hashes, python=sys.version,
        started_at_utc=datetime.now(timezone.utc).isoformat(), per_child_timeout_seconds=300,
        new_gpu_jobs=0, api_calls=0, model_fits=0)
    (output/'execution_context.json').write_text(json.dumps(context, sort_keys=True, indent=2)+'\n')
    records=[]
    failed=False
    for name in ('producer_a','producer_b'):
        cmd=[sys.executable,'-B','-m','phase1.historical_reuse_execution_readiness']
        started=time.monotonic()
        try:
            proc=subprocess.run(cmd,cwd=root,env=env,capture_output=True,timeout=300)
            stdout,stderr,rc=proc.stdout,proc.stderr,proc.returncode
        except subprocess.TimeoutExpired as exc:
            stdout,stderr,rc=exc.stdout or b'',exc.stderr or b'',124
        (output/(name+'.json')).write_bytes(stdout)
        row=dict(name=name,source_commit=source_commit,command=json.dumps(cmd),rc=rc,
            seconds=time.monotonic()-started,stderr_bytes=len(stderr),
            stderr_sha256=hashlib.sha256(stderr).hexdigest(),new_gpu_jobs=0,model_fits=0,api_calls=0)
        records.append(row)
        print(json.dumps(row),flush=True)
        if rc or stderr:
            failed=True
            break
    with (output/'runs.csv').open('x',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(records[0]))
        writer.writeheader();writer.writerows(records)
    if not failed:
        if (output/'producer_a.json').read_bytes() != (output/'producer_b.json').read_bytes():
            failed=True
        if {p:sha(root/p) for p in source_paths} != source_hashes:
            failed=True
    if not failed:
        result=json.loads((output/'producer_a.json').read_bytes())
        if (result['status']!='REUSE_EXECUTION_PLANS_VERIFIED_EFFECT_BLOCKED'
                or len(result['plans'])!=30 or len(result['independent_replays'])!=30
                or len(result['cross_arm_relations'])!=6 or result['new_budget_adopted']):
            failed=True
    marker='FAILED' if failed else 'COMPLETE'
    (output/marker).write_text(marker+'\n')
    manifest={p.name:sha(p) for p in sorted(output.iterdir()) if p.is_file()}
    (output/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    if failed:
        print(json.dumps(dict(status='FAILED_CLOSED',reason='see_preserved_rc_and_safe_output')))
        return 1
    print(json.dumps(dict(status='REUSE_PLAN_CHAIN_COMPLETE',receipt_sha256=sha(output/'producer_a.json'),
        prefix_savings=result['hypothetical_prefix_savings'],new_gpu_jobs=0,model_fits=0)))
    return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source-commit',required=True)
    args=parser.parse_args()
    raise SystemExit(run(args.output.absolute(),args.source_commit))
