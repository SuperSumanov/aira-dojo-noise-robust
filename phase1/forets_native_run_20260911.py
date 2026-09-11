"""Fixed fresh-start exploration entry; no automatic submission or task replay."""
import argparse
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from forets_native_context_20260911 import ROOT, release
from forets_block_runtime_20260911 import execute_block, write_once


def verify_code(directory):
    record = json.loads((directory/'code-manifest.json').read_text())
    if not re.fullmatch('[0-9a-f]{40}', record.get('commit', '')):
        raise ValueError('code commit absent')
    for relative, digest in record['files'].items():
        path = directory/relative
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError('code file escapes release')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('released code changed')
    return record['commit']


def static_ready(directory, block):
    from forets_block_controller_20260911 import inspect_draft
    from forets_e2e_critic_service import SOURCE
    from forets_stage_gate import prior_compatibility
    from forets_opencl_allowlist_20260911 import IMAGE
    commit = verify_code(directory)
    raw = (directory/'forets_native_e2e_release_20260911.json').read_bytes()
    spec = release(raw)
    actual, configs = inspect_draft(ROOT, block)
    if len(configs) != 4: raise ValueError('fixed full block required')
    for name, key in (('bradley_terry_server.py','server_sha256'),
                      ('bradley_terry_evaluation.py','loader_sha256')):
        if hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() != spec[key]:
            raise ValueError('deployed critic input code changed')
    prior_compatibility('gpu28', IMAGE)
    if (ROOT/f'block-{block}.runtime').exists():
        raise ValueError('block already attempted; no automatic resume')
    batch_key=hashlib.sha256('\n'.join(sorted(actual.run_ids)).encode()).hexdigest()[:12]
    if (ROOT/'runs'/'srun_pool'/batch_key).exists():
        raise ValueError('pool already exists; do not resume or overwrite it')
    if not os.access(directory/'bin'/'singularity', os.X_OK):
        raise ValueError('adapter wrapper is not executable')
    return raw, commit


def route(directory, block):
    """Only remote credential + current catalog + two bounded public fixtures."""
    raw, commit = static_ready(directory, block)
    spec = release(raw)
    target = ROOT/f'block-{block}.route.json'
    if target.exists(): raise ValueError('route receipt already exists; review expiry instead of overwriting')
    from forets_e2e_campaign import install_process_credential
    from forets_stage_gate import validate_route_receipt
    from datetime import datetime, timezone
    # Keep any SDK/proxy diagnostics out of logs and never report balances.
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        install_process_credential()
        credential = os.environ.get('OPENROUTER_API_KEY')
        if not credential: raise RuntimeError('known remote credential absent')
        import httpx
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            key = client.get('https://openrouter.ai/api/v1/key', headers={'Authorization':'Bearer '+credential})
            if key.status_code != 200: raise RuntimeError('credential not accepted')
            catalog = client.get('https://openrouter.ai/api/v1/models')
            catalog.raise_for_status()
            matches = [x for x in catalog.json().get('data',[]) if x.get('id')==spec['generator']]
            if len(matches)!=1: raise RuntimeError('fixed free model absent')
            entry=matches[0]
            if any(float(entry.get('pricing',{}).get(k,'nan'))!=0 for k in ('prompt','completion')):
                raise RuntimeError('fixed route no longer free')
            if not {'tools','tool_choice'} <= set(entry.get('supported_parameters',[])):
                raise RuntimeError('fixed route missing required capabilities')
    write_once(ROOT/f'block-{block}.catalog.json', dict(utc=datetime.now(timezone.utc).isoformat(),
        model=spec['generator'],prompt_price_zero=True,completion_price_zero=True,
        tools_supported=True,credential_http_status=200,controller_commit=commit))
    output=ROOT/f'block-{block}.route-check'
    result=subprocess.run([sys.executable,'-B',str(directory/'check_forets_resilience_live_20260910.py'),
        '--source',str(ROOT/'source'),'--package',str(ROOT),'--output',str(output),
        '--max-attempts','3'],capture_output=True,text=True,timeout=800)
    report=json.loads((output/'finished.json').read_text()) if (output/'finished.json').exists() else {}
    if result.returncode or report.get('status')!='READY':
        print(json.dumps(dict(status='ROUTE_NOT_READY_NO_GPU',block=block,
            report=str(output/'finished.json'),returncode=result.returncode)),flush=True)
        return 2
    write_once(target,report)
    validate_route_receipt(target,ROOT/'source')
    print(json.dumps(dict(status='ROUTE_READY',block=block,reserved_attempts=report.get('reserved_attempts'),
        logical_requests=len(report.get('calls',[])),receipt=str(target))),flush=True)
    return 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('inspect','route','execute'))
    p.add_argument('--block',type=int,choices=(1,2),required=True)
    args=p.parse_args();directory=Path(__file__).resolve().parent
    os.environ.update(PYTHON_DOTENV_DISABLED='1',PYTHONDONTWRITEBYTECODE='1')
    if args.mode=='route':return route(directory,args.block)
    raw,commit=static_ready(directory,args.block)
    if args.mode=='inspect':
        print(json.dumps(dict(status='STATIC_READY_NOT_SUBMITTED',block=args.block,commit=commit,
            historical_input_template='unknown_fixed_existing_service',model_calls=0,api_calls=0)))
        return 0
    if (not os.environ.get('SLURM_JOB_ID','').isdigit()
            or os.environ.get('SLURM_STEP_ID','') not in ('','batch')):
        raise RuntimeError('dedicated batch allocation required before credentials')
    from forets_stage_gate import validate_route_receipt
    validate_route_receipt(ROOT/f'block-{args.block}.route.json',ROOT/'source')
    from forets_e2e_campaign import install_process_credential
    install_process_credential()
    status=execute_block(ROOT,args.block,raw,node='gpu28',controller_commit=commit)
    print(json.dumps(status),flush=True)
    return 0 if status['status']=='completed' else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print(json.dumps(dict(status='STOPPED',error_type=type(exc).__name__)),flush=True)
        raise SystemExit(2)
