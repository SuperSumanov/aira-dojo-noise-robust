"""Run bounded, CPU-only metadata production and independent verification."""
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

SOURCES=['phase1/historical_label_reuse_support.py',
         'phase1/verify_historical_label_reuse_support.py',
         'phase1/scripts/run_historical_label_reuse_support_20260904.py']


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--source-commit',required=True); a=ap.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',a.source_commit):
        raise ValueError('exact_commit_required')
    a.output.mkdir(mode=0o700,exist_ok=False)
    sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES}
    config=dict(source_commit=a.source_commit,source_sha256=sources,python=sys.version,
        started_at_utc=datetime.now(timezone.utc).isoformat(),child_timeout_seconds=180,
        planned_executions=['producer_a','producer_b','independent'],
        learning_seed='not_applicable',warmup='not_applicable',new_gpu_jobs=0,model_fits=0,api_calls=0)
    (a.output/'execution_context.json').write_text(json.dumps(config,sort_keys=True,indent=2)+'\n')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='0',
             OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    rows=[]
    def child(name,module,extra=()):
        command=[sys.executable,'-B','-m',module,*extra]; start=time.monotonic()
        result=subprocess.run(command,env=env,capture_output=True,timeout=180)
        (a.output/(name+'.json')).write_bytes(result.stdout)
        rows.append(dict(name=name,source_commit=a.source_commit,command=json.dumps(command),
            rc=result.returncode,elapsed_seconds=time.monotonic()-start,stderr_bytes=len(result.stderr),
            stderr_sha256=hashlib.sha256(result.stderr).hexdigest(),new_gpu_jobs=0,model_fits=0,api_calls=0))
        with (a.output/'runs.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        if result.returncode or result.stderr:
            raise ValueError('child_failed_closed')
        json.loads(result.stdout)
        print(json.dumps(dict(stage=name,rc=0,elapsed_seconds=rows[-1]['elapsed_seconds'])),flush=True)
    try:
        for name in ('producer_a','producer_b'):
            child(name,'phase1.historical_label_reuse_support')
        raw=(a.output/'producer_a.json').read_bytes()
        if raw!=(a.output/'producer_b.json').read_bytes():
            raise ValueError('ab_byte_drift')
        sha=hashlib.sha256(raw).hexdigest()
        child('independent','phase1.verify_historical_label_reuse_support',
              ['--receipt',str((a.output/'producer_a.json').resolve()),'--sha256',sha])
        if sources!={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in SOURCES}:
            raise ValueError('source_drift')
        metrics=json.loads(raw)['metrics']
        (a.output/'COMPLETE').write_text('HISTORICAL_SUPPORT_VERIFIED_NOT_EFFECT\n')
        print(json.dumps(dict(status='LABEL_REUSE_SUPPORT_COMPLETE',receipt_sha256=sha,metrics=metrics),sort_keys=True))
    except Exception as exc:
        (a.output/'FAILED').write_text(type(exc).__name__+'\n')
        raise
    finally:
        manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.output.iterdir() if p.is_file()}
        (a.output/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(status='WRAPPER_FAILED_CLOSED',exception_type=type(exc).__name__)))
        raise SystemExit(1)
