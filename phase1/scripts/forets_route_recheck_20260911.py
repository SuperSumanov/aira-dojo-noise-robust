"""One additional fixed two-attempt window; preserve the failed first window."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

CODE = Path('/research/d7/spc/yzyang4/forets-native-release-20260911-dAKj2b')
ROOT = Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4')


def main():
    sys.path.insert(0, str(CODE))
    from forets_native_run_20260911 import static_ready, release, write_once
    from forets_e2e_campaign import install_process_credential
    from forets_stage_gate import validate_route_receipt
    raw, commit = static_ready(CODE, 1)
    spec = release(raw)
    target = ROOT/'block-1.route.json'
    output = ROOT/'block-1.route-recheck-1'
    if target.exists() or output.exists():
        raise RuntimeError('existing receipt/window; no automatic repeats')
    old_path = ROOT/'block-1.route-check/finished.json'
    old_raw = old_path.read_bytes()
    if hashlib.sha256(old_raw).hexdigest() != 'b93687e9f2aa60d1151cea56de3adc5f6092ab62d0df71ecd6166fdb1b9e998d':
        raise RuntimeError('failed window changed')
    # Lock the single extra window before any credential or network access.
    write_once(ROOT/'block-1.recheck-1-intent.json', dict(
        utc=datetime.now(timezone.utc).isoformat(), controller_commit=commit,
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        old_finished_sha256=hashlib.sha256(old_raw).hexdigest(),
        additional_generation_attempt_cap=2, attempts_per_logical_request=1,
        timeout_per_attempt_seconds=120, model=spec['generator'],
        config_or_model_changes=False, gpu_jobs=0))
    with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
        install_process_credential()
        import httpx
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            key = client.get('https://openrouter.ai/api/v1/key',
                headers={'Authorization': 'Bearer '+os.environ['OPENROUTER_API_KEY']})
            if key.status_code != 200:
                raise RuntimeError('credential not accepted')
            response = client.get('https://openrouter.ai/api/v1/models')
            response.raise_for_status()
            rows = [r for r in response.json()['data'] if r.get('id') == spec['generator']]
            if len(rows) != 1 or any(float(rows[0].get('pricing', {}).get(k, 'nan')) != 0
                                     for k in ('prompt', 'completion')):
                raise RuntimeError('fixed model no longer listed free')
            if not {'tools', 'tool_choice'} <= set(rows[0].get('supported_parameters', [])):
                raise RuntimeError('required tool support absent')
    write_once(ROOT/'block-1.recheck-1-catalog.json', dict(
        utc=datetime.now(timezone.utc).isoformat(), model=spec['generator'],
        credential_http_status=200, prompt_price_zero=True, completion_price_zero=True,
        tools_supported=True, controller_commit=commit))
    result = subprocess.run([sys.executable, '-B', str(CODE/'check_forets_resilience_live_20260910.py'),
        '--source', str(ROOT/'source'), '--package', str(ROOT), '--output', str(output),
        '--max-attempts', '1'], capture_output=True, timeout=300)
    report_path = output/'finished.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    if (result.returncode != 0 or report.get('status') != 'READY'
            or report.get('reserved_attempts') != 2):
        print(json.dumps(dict(status='NOT_READY_NO_GPU', returncode=result.returncode,
                              report=str(report_path))), flush=True)
        return 2
    verified = validate_route_receipt(report_path, ROOT/'source')
    # Validate the new successful artifact BEFORE publishing it for production.
    with target.open('xb') as stream:
        stream.write(report_path.read_bytes())
    assert validate_route_receipt(target, ROOT/'source') == verified
    print(json.dumps(dict(status='READY', receipt=str(target), **verified)), flush=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps(dict(status='STOPPED_NO_GPU', error_type=type(exc).__name__)), flush=True)
        raise SystemExit(2)
