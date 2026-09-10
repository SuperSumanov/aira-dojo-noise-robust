"""Two public-fixture calls, <=6 reserved attempts, no GPU/task/secret output."""
import argparse
import asyncio
from contextlib import redirect_stdout, redirect_stderr
import datetime
import io
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--max-attempts', type=int, choices=(1, 3), default=3)
    args = p.parse_args()
    args.output.mkdir(mode=0o700, exist_ok=False)
    os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHON_DOTENV_DISABLED='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
        LOGGING_DIR=str(args.output), MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0, str(args.source/'src'))
    report = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='NOT_READY', generation_attempt_cap=2*args.max_attempts, logical_request_cap=2,
        timeout_per_attempt_seconds=120, output_tokens_per_attempt=8192,
        gpu_jobs=0, task_runs=0, public_artificial_input_only=True, calls=[])
    report['source_hashes'] = {name:hashlib.sha256((args.source/'src/dojo/core/solvers/llm_helpers/backends'/name).read_bytes()).hexdigest()
                             for name in ('lite_llm.py', 'bounded_retry.py')}
    def save(name, value):
        with os.fdopen(os.open(args.output/name, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600), 'w') as f:
            json.dump(value, f, indent=2)
            f.write('\n')
    save('started.json', report)
    captured = io.StringIO()
    budget = None
    with redirect_stdout(captured), redirect_stderr(captured):
        try:
            from dotenv import dotenv_values
            credential = dotenv_values('/research/d7/spc/yzyang4/aira-dojo/.env', interpolate=False).get('OPENROUTER_API_KEY')
            if not credential:
                raise RuntimeError('remote provider entry absent')
            os.environ['PRIMARY_KEY'] = credential
            from dojo.config_dataclasses.run import RunConfig
            from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
            from dojo.core.solvers.llm_helpers.backends.run_budget import initialize
            from dojo.core.solvers.llm_helpers.backends.bounded_retry import BoundedAttemptError
            manifest = json.loads((args.package/'manifest.json').read_text())
            cfg = RunConfig.load_from_json(args.package/'configs'/(manifest['runs'][0]['run_id']+'.json'))
            report['model'] = cfg.solver.operators['draft'].llm.client.model_id
            llm = GenericLLM(cfg.solver.operators['draft'])
            llm.generation_kwargs['bounded_max_attempts'] = args.max_attempts
            budget = Path(tempfile.mkdtemp(prefix='forets-resilience-live-',dir='/tmp'))/'attempts.sqlite'
            initialize(budget, 2*args.max_attempts, 8192)
            os.environ['FORETS_RUN_BUDGET_PATH'] = str(budget)
            async def exercise():
                for index in range(2):
                    row = dict(index=index, fixture_matched=False)
                    try:
                        value, info = await llm(messages=[dict(role='user', content='Public artificial connectivity check. Call emit with code exactly print(1). No other text is needed.')],
                            json_schema=json.dumps(dict(type='object', required=['code'], additionalProperties=False,
                                properties=dict(code=dict(type='string')))),
                            function_name='emit', function_description='Return artificial test code.')
                        row['fixture_matched'] = isinstance(value, dict) and value.get('code', '').strip() == 'print(1)'
                        usage = info.get('usage', {})
                        row['usage'] = {k:usage.get(k) for k in ('adapter_attempts','prompt_tokens','completion_tokens','total_tokens','cost')}
                    except BoundedAttemptError as exc:
                        row['error'] = {k:exc.event.get(k) for k in ('error_type','http_status','retryable')}
                    except Exception as exc:
                        row['error'] = dict(error_type=type(exc).__name__)
                    report['calls'].append(row)
            asyncio.run(exercise())
            report['status'] = 'READY' if all(x['fixture_matched'] for x in report['calls']) else 'NOT_READY'
        except Exception as exc:
            report['setup_error_type'] = type(exc).__name__
    events = {}
    for line in captured.getvalue().splitlines():
        if 'bounded_transport {' not in line: continue
        try:
            event = json.loads(line.split('bounded_transport ',1)[1])
        except ValueError:
            continue
        events[event['attempt_id']] = {k:event.get(k) for k in
            ('state','success','error_type','http_status','retryable','latency','run_attempt_ordinal')}
    report['transport_events'] = list(events.values())
    captured.close()
    if budget is not None:
        with sqlite3.connect(budget.as_uri()+'?mode=ro', uri=True) as db:
            report['reserved_attempts'] = db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
    save('finished.json', report)
    print(json.dumps(report))
    raise SystemExit(0 if report['status'] == 'READY' else 1)


if __name__ == '__main__': main()
