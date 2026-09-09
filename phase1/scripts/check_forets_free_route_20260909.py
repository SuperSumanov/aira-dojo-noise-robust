"""New free-route integration only: real Hydra/SDK, artificial loopback server.

No .env, external API, GPU, corpus, model, or task execution. This does not test
OpenRouter account access, free-provider availability, billing or model quality.
"""
import argparse
import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
from unittest.mock import patch


EXPECTED = {
    'litellm_nemotron-3-ultra': 'nvidia/nemotron-3-ultra-550b-a55b:free',
    'litellm_laguna-s-2.1': 'poolside/laguna-s-2.1:free',
}
PROVIDER = dict(allow_fallbacks=False, require_parameters=True,
                max_price=dict(prompt=0, completion=0, request=0))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dojo-root', required=True, type=Path)
    p.add_argument('--plan-root', required=True, type=Path)
    p.add_argument('--source-tree', required=True)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise RuntimeError('existing receipt; do not rerun')
    # Do not read credentials or task paths. Imported clients get no real key.
    for key in tuple(os.environ):
        if key.startswith('PRIMARY_KEY') or key in ('OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'FORETS_RUN_BUDGET_PATH'):
            del os.environ[key]
    os.environ.update(CUDA_VISIBLE_DEVICES='', LITELLM_LOCAL_MODEL_COST_MAP='True',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1',
        NO_PROXY='127.0.0.1,localhost', LOGGING_DIR='/tmp', DEFAULT_SLURM_PARTITION='gpu_24h',
        DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu',
        MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread')
    os.chdir(args.dojo_root)
    sys.path[:0] = [str(args.dojo_root / 'src'), str(args.plan_root)]
    observed, paired_hashes, configs = [], [], {}
    sdk_errors = []
    denied_connections = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            assert self.path == '/v1/chat/completions'
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            observed.append(body)  # artificial body only, not headers
            data = dict(id='synthetic', object='chat.completion', created=1, model=body['model'],
                choices=[dict(index=0, finish_reason='tool_calls', message=dict(role='assistant',
                    content=None, tool_calls=[dict(id='synthetic-call', type='function',
                    function=dict(name='emit', arguments='{"code":"print(1)"}'))]))],
                usage=dict(prompt_tokens=3, completion_tokens=4, total_tokens=7))
            payload = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_connect = socket.socket.connect
    address = server.server_address

    def local_connect(sock, target):
        if not isinstance(target, tuple) or target[:2] != address:
            denied_connections.append(True)
            raise AssertionError('external connection denied')
        return original_connect(sock, target)

    try:
        with tempfile.TemporaryDirectory(prefix='forets-free-route-', dir='/tmp') as tmp, \
                patch.object(socket.socket, 'connect', local_connect):
            from forets_pilot_plan import overrides, run_order, free_route_overrides, bounded_launcher_overrides
            from dojo.config_dataclasses.omegaconf.resolvers import register_new_resolvers
            from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
            from dojo.core.solvers.llm_helpers.backends import lite_llm as backend
            from dojo.utils.run_budget import initialize
            from hydra import compose, initialize_config_dir
            from hydra.utils import instantiate
            from omegaconf import OmegaConf
            register_new_resolvers()
            real_completion = backend.completion_fn

            async def checked_completion(**kwargs):
                try:
                    return await real_completion(**kwargs)
                except Exception as exc:
                    # Only a synthetic credential/artificial input can reach this
                    # loopback-only test; no production exception text is exposed.
                    sdk_errors.append(dict(type=type(exc).__name__,
                        message=str(exc).replace('synthetic', '[fixture]')[:1500]))
                    raise
            for invalid in ('litellm_deepseek_flash', 'poolside/laguna-s-2.1', ''):
                try:
                    free_route_overrides(invalid)
                except ValueError:
                    pass
                else:
                    raise AssertionError('unknown/paid client accepted')

            for alias, model in EXPECTED.items():
                hashes = []
                for task, seed, policy in run_order():
                    ov = overrides(task, seed, policy, max_output_tokens=32, request_timeout_seconds=5)
                    ov += bounded_launcher_overrides(max_api_attempts=4, max_output_tokens=32)
                    ov += free_route_overrides(alias)
                    with initialize_config_dir(config_dir=str(args.dojo_root / 'src/dojo/configs'), version_base=None):
                        config = compose(config_name='default_runner', overrides=ov)
                    solver = instantiate(config.solver)
                    solver.validate()
                    plain = OmegaConf.to_container(config, resolve=True)
                    assert plain['logger']['write_env_vars'] is False
                    for op in ('draft', 'improve', 'debug', 'analyze'):
                        entry = plain['solver']['operators'][op]['llm']
                        assert entry['client']['model_id'] == model
                        assert entry['client']['base_url'] == 'https://openrouter.ai/api/v1'
                        kw = entry['generation_kwargs']
                        assert kw['structured_output_mode'] == 'tools'
                        assert kw['extra_body']['provider'] == PROVIDER
                        assert kw['bounded_transport'] is True and kw['bounded_run_budget_required'] is True
                        assert kw['max_tokens'] == 32 and kw['structured_output_retries'] == 0
                        assert not {'model', 'models', 'fallbacks', 'api_key', 'base_url'} & kw.keys()
                    configs.setdefault(alias, solver)
                    del plain['solver']['selection_policy']
                    hashes.append(hashlib.sha256(json.dumps(plain, sort_keys=True).encode()).hexdigest())
                assert len(hashes) == 8
                assert all(hashes[i] == hashes[i+1] for i in range(0, 8, 2))
                paired_hashes.append(dict(alias=alias, hashes=hashes[::2]))

            async def check_payloads():
                for index, (alias, model) in enumerate(EXPECTED.items()):
                    ledger = Path(tmp) / ('budget-' + str(index) + '.sqlite')
                    initialize(ledger, 4, 32)
                    os.environ['FORETS_RUN_BUDGET_PATH'] = str(ledger)
                    for op in ('draft', 'improve', 'debug', 'analyze'):
                        operator = GenericLLM(configs[alias].operators[op])
                        assert not operator.client.api_key
                        assert operator.client.model == 'openai/' + model
                        operator.client.base_url = 'http://127.0.0.1:' + str(address[1]) + '/v1'
                        operator.client.api_key = 'synthetic'
                        before = len(observed)
                        assert type(operator.generation_kwargs) is dict
                        assert type(operator.generation_kwargs['extra_body']) is dict
                        assert type(operator.generation_kwargs['extra_body']['provider']) is dict
                        output, info = await operator(
                            messages=[dict(role='user', content='Artificial test: emit print(1).')],
                            json_schema=json.dumps(dict(type='object', required=['code'],
                                properties=dict(code=dict(type='string')), additionalProperties=False)),
                            function_name='emit', function_description='Artificial code output')
                        stats = info['usage']
                        assert output == {'code': 'print(1)'} and stats['cost'] is None
                        assert stats['structured_output_transport'] == 'tools'
                        assert len(observed) == before + 1
                        body = observed[-1]
                        assert body['model'] == model and body['max_tokens'] == 32
                        assert body['provider'] == PROVIDER
                        assert body['tools'][0]['function']['name'] == 'emit'
                        assert body['tool_choice'] == dict(type='function', function=dict(name='emit'))
                        assert not {'response_format', 'models', 'fallbacks'} & body.keys()
            with patch.object(backend, 'completion_fn', checked_completion):
                asyncio.run(check_payloads())
    except Exception as exc:
        failure = dict(status='FREE_ROUTE_CHECK_FAILED', error_type=type(exc).__name__,
            local_http_requests=len(observed), completed_config_groups=len(paired_hashes),
            sdk_errors=sdk_errors, denied_external_connections=len(denied_connections),
            external_api_calls=0, source_tree=args.source_tree)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x') as f:
            json.dump(failure, f, sort_keys=True, indent=2)
        print(json.dumps(failure, sort_keys=True))
        raise
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert len(observed) == 8 and not denied_connections
    report = dict(status='FREE_ROUTE_CONFIGURATION_AND_LOOPBACK_PASS', source_tree=args.source_tree,
        plan_sha256=hashlib.sha256((args.plan_root/'forets_pilot_plan.py').read_bytes()).hexdigest(),
        test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        resolved_config_count=16, local_http_requests=len(observed), paired_config_hashes=paired_hashes,
        checks=['reject_unknown_or_paid_alias', 'four_operators_same_confirmed_free_route',
                'whole_paired_config_only_selector_differs', 'real_sdk_tools_and_zero_price_body'],
        external_api_calls=0, denied_external_connections=len(denied_connections), gpu_requested=False,
        model_loaded=False, task_executed=False, protected_data_read=False,
        provider_billing_verified=False, live_endpoint_verified=False,
        versions={name:importlib.metadata.version(name) for name in ('litellm','openai','httpx','hydra-core')})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as f:
        json.dump(report, f, sort_keys=True, indent=2)
        f.write('\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
