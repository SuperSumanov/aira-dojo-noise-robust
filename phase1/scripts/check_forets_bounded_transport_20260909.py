"""Actual LiteLLM-client tests with artificial completion_fn; no real HTTP/API."""
import argparse
import asyncio
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import socket
import sys
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dojo-root', type=Path, required=True)
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    os.environ.update(CUDA_VISIBLE_DEVICES='', LITELLM_LOCAL_MODEL_COST_MAP='True')
    sys.path.insert(0, str(args.dojo_root / 'src'))
    checks = []
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
        spec = importlib.util.spec_from_file_location('bounded_backend', args.backend)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        client = module.LiteLLMClient.__new__(module.LiteLLMClient)
        client.model, client.base_url, client.api_key, client.provider = 'artificial', 'http://invalid.invalid', '', 'openai'
        params = dict(messages=[{'role': 'user', 'content': 'artificial'}],
                      json_schema=json.dumps({'type': 'object', 'properties': {'code': {'type': 'string'}},
                                              'required': ['code']}),
                      function_name='emit', function_description='artificial',
                      model_kwargs=dict(bounded_transport=True, bounded_request_timeout_seconds=.1, max_tokens=32,
                                        structured_output_retries=9))
        def response(body='{"code":"print(1)"}', usage=None):
            return NS(choices=[NS(message=NS(content=body))], to_dict=lambda: {'usage': usage})
        logs = io.StringIO()
        handler = logging.StreamHandler(logs)
        module.logger.addHandler(handler)
        async def exercise():
            valid = AsyncMock(return_value=response(usage={'prompt_tokens': 3, 'completion_tokens': 4}))
            with patch.object(module, 'completion_fn', valid):
                out, usage = await client._query_client(**params)
            assert out == {'code': 'print(1)'} and valid.await_count == 1
            assert valid.call_args.kwargs['max_retries'] == valid.call_args.kwargs['num_retries'] == 0
            assert 'bounded_transport' not in valid.call_args.kwargs
            assert usage['total_tokens'] == 7 and usage['cost'] is None
            checks.append('one_attempt_no_sdk_retry_unpriced_not_zero')
            for label, bad in [('missing', None), ('boolean', {'prompt_tokens': True, 'completion_tokens': 3})]:
                with patch.object(module, 'completion_fn', AsyncMock(return_value=response(usage=bad))):
                    _, usage = await client._query_client(**params)
                assert usage['total_tokens'] is None and usage['cost'] is None
                checks.append('unknown_usage_' + label)
            for label, mocked in [
                ('schema', AsyncMock(return_value=response('{"code":2}', {'prompt_tokens': 2, 'completion_tokens': 2}))),
                ('transport', AsyncMock(side_effect=TimeoutError('artificial private exception'))),
                ('unsupported_json', AsyncMock(side_effect=module.litellm.BadRequestError(
                    message='response_format json_object not supported artificial private exception',
                    model='artificial', llm_provider='openai'))),
            ]:
                with patch.object(module, 'completion_fn', mocked):
                    try:
                        await client._query_client(**params)
                        raise AssertionError('expected bounded failure')
                    except RuntimeError as exc:
                        assert 'private exception' not in str(exc)
                assert mocked.await_count == 1
                checks.append('no_retry_or_fallback_' + label)
            async def hangs(**kwargs):
                await asyncio.sleep(20)
            start = asyncio.get_running_loop().time()
            with patch.object(module, 'completion_fn', hangs):
                try:
                    await client._query_client(**params)
                    raise AssertionError('deadline ignored')
                except RuntimeError:
                    pass
            assert asyncio.get_running_loop().time() - start < 1
            checks.append('await_deadline_cancels_local_call')
            # Omitted opt-in retains upstream default behavior, including legacy cost semantics.
            legacy_params = dict(params, model_kwargs={'max_tokens': 32})
            legacy = AsyncMock(return_value=response(usage={'prompt_tokens': 1, 'completion_tokens': 1}))
            with patch.object(module, 'completion_fn', legacy):
                await client._query_client(**legacy_params)
            assert legacy.call_args.kwargs['max_retries'] == module.NUM_RETRIES
            checks.append('legacy_without_opt_in_unchanged')
        asyncio.run(exercise())
        module.logger.removeHandler(handler)
        events = [json.loads(line.split('bounded_transport ', 1)[1]) for line in logs.getvalue().splitlines()
                  if line.startswith('bounded_transport ')]
        assert events and all('code' not in e and 'messages' not in e and e['cost'] is None for e in events)
        assert 'private exception' not in logs.getvalue()
        assert any(e['state'] == 'transport_unknown' for e in events)
        assert any(e['state'] == 'response_invalid' and e['prompt_tokens'] == 2 for e in events)
        checks.append('safe_attempt_events_include_failed_usage')
    report = dict(status='CPU_TRANSPORT_CHECK_PASS', checks=checks, checks_passed=len(checks),
                  gpu_requested=False, api_calls=0, protected_data_read=False,
                  actual_provider_retries_verified=False, monetary_cap_verified=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
