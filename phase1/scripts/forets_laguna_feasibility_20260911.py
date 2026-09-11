"""Two public calls on the other senior-approved free client; never releases a block."""
import asyncio
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

CODE = Path('/research/d7/spc/yzyang4/forets-native-release-20260911-dAKj2b')
ROOT = Path('/research/d7/spc/yzyang4/forets-next-config-20260911-4h_0y6b4')
OUTPUT = Path('/research/d7/spc/yzyang4/forets-laguna-feasibility-20260911-v1')
MODEL = 'poolside/laguna-s-2.1:free'


def main():
    OUTPUT.mkdir(mode=0o700, exist_ok=False)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
        CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', LOGGING_DIR=str(OUTPUT),
        MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0, str(CODE))
    from forets_native_run_20260911 import static_ready, write_once
    from forets_e2e_campaign import install_process_credential
    _, commit = static_ready(CODE, 1)
    report = dict(utc=datetime.now(timezone.utc).isoformat(), status='NOT_READY',
        role='alternate_free_route_feasibility_not_production_release', model=MODEL,
        controller_commit=commit, checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        logical_request_cap=2, generation_attempt_cap=2, timeout_per_attempt_seconds=120,
        output_tokens_per_attempt=8192, public_artificial_input_only=True,
        production_config_modified=False, gpu_jobs=0, task_runs=0, calls=[])
    write_once(OUTPUT/'started.json', report)
    captured = io.StringIO()
    budget = None
    with redirect_stdout(captured), redirect_stderr(captured):
        try:
            install_process_credential()
            os.environ['PRIMARY_KEY'] = os.environ['OPENROUTER_API_KEY']
            import httpx
            with httpx.Client(timeout=30, follow_redirects=False) as client:
                key = client.get('https://openrouter.ai/api/v1/key',
                    headers={'Authorization': 'Bearer '+os.environ['OPENROUTER_API_KEY']})
                if key.status_code != 200: raise RuntimeError('credential not accepted')
                response = client.get('https://openrouter.ai/api/v1/models/'+MODEL+'/endpoints')
                response.raise_for_status()
                endpoints = response.json()['data']['endpoints']
                required = {'tools', 'tool_choice', 'max_tokens', 'temperature'}
                eligible = [e for e in endpoints if required <= set(e.get('supported_parameters', []))
                    and all(float(e.get('pricing', {}).get(k, 'nan')) == 0 for k in ('prompt', 'completion'))]
                if not eligible: raise RuntimeError('free compatible endpoint absent')
                report['catalog'] = dict(credential_http_status=200, free_compatible_endpoints=len(eligible),
                    required_parameters=sorted(required), top_p_omitted=True,
                    endpoint_metadata_utc=datetime.now(timezone.utc).isoformat())
            sys.path.insert(0, str(ROOT/'source/src'))
            from dojo.config_dataclasses.run import RunConfig
            from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
            from dojo.core.solvers.llm_helpers.backends.run_budget import initialize
            from dojo.core.solvers.llm_helpers.backends.bounded_retry import BoundedAttemptError
            prepared = json.loads((ROOT/'prepared.json').read_text())
            path = ROOT/'configs'/(prepared['run_configs'][0]['run_id']+'.json')
            before = path.read_bytes()
            cfg = RunConfig.load_from_json(path)
            op = cfg.solver.operators['draft']
            op.llm.client.model_id = MODEL
            op.llm.generation_kwargs.pop('top_p', None)
            op.llm.generation_kwargs['bounded_max_attempts'] = 1
            llm = GenericLLM(op)
            report['input_changes'] = dict(model_id=MODEL, top_p='omitted',
                max_attempts=1, original_config_sha256=hashlib.sha256(before).hexdigest())
            budget = Path(tempfile.mkdtemp(prefix='forets-laguna-fixture-', dir='/tmp'))/'attempts.sqlite'
            initialize(budget, 2, 8192)
            os.environ['FORETS_RUN_BUDGET_PATH'] = str(budget)
            async def run():
                for index in range(2):
                    row = dict(index=index, fixture_matched=False)
                    try:
                        value, info = await llm(messages=[dict(role='user', content=
                            'Public artificial connectivity check. Call emit with code exactly print(1). No other text is needed.')],
                            json_schema=json.dumps(dict(type='object', required=['code'], additionalProperties=False,
                                properties=dict(code=dict(type='string')))),
                            function_name='emit', function_description='Return artificial test code.')
                        row['fixture_matched'] = isinstance(value, dict) and value.get('code', '').strip() == 'print(1)'
                        row['usage'] = {k:info.get('usage', {}).get(k) for k in
                            ('adapter_attempts', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'cost')}
                    except BoundedAttemptError as exc:
                        row['error'] = {k:exc.event.get(k) for k in ('error_type','http_status','retryable')}
                    except Exception as exc:
                        row['error'] = dict(error_type=type(exc).__name__)
                    report['calls'].append(row)
            asyncio.run(run())
            if path.read_bytes() != before: raise RuntimeError('original configuration changed')
            if len(report['calls']) == 2 and all(r['fixture_matched'] for r in report['calls']):
                report['status'] = 'FEASIBLE_NOT_RELEASED'
        except Exception as exc:
            report['setup_error_type'] = type(exc).__name__
    events = {}
    for line in captured.getvalue().splitlines():
        if 'bounded_transport {' not in line: continue
        try: event = json.loads(line.split('bounded_transport ', 1)[1])
        except ValueError: continue
        events[event['attempt_id']] = {k:event.get(k) for k in
            ('state','success','error_type','http_status','retryable','latency','run_attempt_ordinal')}
    captured.close()
    report['transport_events'] = list(events.values())
    if budget is not None:
        with sqlite3.connect(budget.as_uri()+'?mode=ro', uri=True) as db:
            report['reserved_attempts'] = db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    write_once(OUTPUT/'finished.json', report)
    print(json.dumps(report), flush=True)
    return 0 if report['status'] == 'FEASIBLE_NOT_RELEASED' else 1


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as exc:
        print(json.dumps(dict(status='STOPPED_NO_GPU',error_type=type(exc).__name__)),flush=True)
        raise SystemExit(2)
