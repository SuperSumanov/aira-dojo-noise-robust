"""CPU integration through installed LiteLLM/SDK into an in-memory HTTP transport."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import importlib.metadata
import io
import json
import logging
import os
import socket
from unittest.mock import patch

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['LITELLM_LOG'] = 'ERROR'
os.environ['HF_HUB_OFFLINE'] = '1'


async def check():
    import httpx
    import litellm
    from openai import AsyncOpenAI
    from omegaconf import OmegaConf
    logging.disable(logging.CRITICAL)
    captured = []
    def respond(request):
        body = json.loads(request.content)
        captured.append(body)
        return httpx.Response(200, json={'id': 'fixture-id', 'object': 'chat.completion', 'created': 0,
            'model': body['model'], 'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'fixture'}}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 2, 'total_tokens': 7}})
    rows = []
    http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    sdk = AsyncOpenAI(api_key='fixture', base_url='https://fixture.invalid/v1', http_client=http, max_retries=0)
    for mode in ('original_minimal', 'nested_unmaterialized', 'explicit_materialized'):
        for model in ('qwen3.5-9b', 'qwen3.5-9b-mle-lora'):
            params = {'reasoning_effort': 'minimal', 'allowed_openai_params': ['reasoning_effort'], 'temperature': 0.6,
                      'top_p': 0.95, 'seed': 101, 'max_tokens': 16}
            if mode != 'original_minimal':
                params['extra_body'] = {'chat_template_kwargs': {'enable_thinking': False}}
            cfg = OmegaConf.create(params)
            outgoing = dict(cfg) if mode == 'nested_unmaterialized' else OmegaConf.to_container(cfg, resolve=True)
            before = len(captured)
            row = {'mode': mode, 'model': model}
            try:
                response = await asyncio.wait_for(litellm.acompletion(model='openai/' + model,
                    messages=[{'role': 'system', 'content': 'fixture'}, {'role': 'user', 'content': 'fixture'}],
                    client=sdk, api_key='fixture', api_base='https://fixture.invalid/v1',
                    max_retries=0, num_retries=0, request_timeout=5, **outgoing), timeout=15)
                row['fixture_response'] = response.choices[0].message.content == 'fixture'
            except Exception as exc:
                row['error_type'] = type(exc).__name__
            row['in_memory_http_requests'] = len(captured) - before
            if row['in_memory_http_requests']:
                b = captured[-1]
                row.update(wire_model=b['model'], wire_effort=b.get('reasoning_effort'), wire_seed=b.get('seed'),
                           wire_enable_thinking=b.get('chat_template_kwargs', {}).get('enable_thinking'))
            rows.append(row)
    await sdk.close()
    assert len(rows) == 6
    assert all(r.get('fixture_response') and r['in_memory_http_requests'] == 1
               and r['wire_model'] == r['model'] and r['wire_effort'] == 'minimal'
               and r['wire_enable_thinking'] is False and r['wire_seed'] == 101
               for r in rows if r['mode'] == 'explicit_materialized')
    assert all(r.get('fixture_response') and r['in_memory_http_requests'] == 1
               and r['wire_model'] == r['model'] and r['wire_effort'] == 'minimal'
               and r['wire_enable_thinking'] is None and r['wire_seed'] == 101
               for r in rows if r['mode'] == 'original_minimal')
    assert all(r.get('error_type') == 'APIError' and r['in_memory_http_requests'] == 0
               for r in rows if r['mode'] == 'nested_unmaterialized')
    return {'utc': datetime.now(timezone.utc).isoformat(), 'status': 'PASS_MOCK_HTTP_ONLY',
            'versions': {n: importlib.metadata.version(n) for n in ('litellm', 'openai', 'httpx', 'omegaconf')},
            'cases': rows, 'external_network_requests': 0, 'model_inferences': 0,
            'limitation': 'Installed client integration validated; live service execution and quality remain untested.'}


def main():
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink), patch.object(socket.socket, 'connect', side_effect=AssertionError('network_forbidden')):
        report = asyncio.run(check())
    print(json.dumps(report))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'error_type': type(exc).__name__})); raise SystemExit(2)
