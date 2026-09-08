"""Observe real LiteLLM HTTP attempts against a local artificial server only."""
import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from unittest.mock import patch


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dojo-root', type=Path, required=True)
    p.add_argument('--backend', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    assert not args.output.exists()
    os.environ.update(CUDA_VISIBLE_DEVICES='', LITELLM_LOCAL_MODEL_COST_MAP='True',
                      NO_PROXY='127.0.0.1,localhost')
    sys.path.insert(0, str(args.dojo_root / 'src'))
    requests, rows = [], []
    fixture = {'status': 200, 'invalid': False}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert self.path == '/v1/chat/completions'
            assert self.headers.get('Authorization') == 'Bearer loopback-only-fixture'
            requests.append({'max_tokens': body.get('max_tokens'), 'case': dict(fixture)})
            status = fixture['status']
            if status == 200:
                data = dict(id='local-test', object='chat.completion', created=1, model='artificial',
                    choices=[dict(index=0, message=dict(role='assistant', content='{}' if fixture['invalid'] else '{"code":"print(1)"}'), finish_reason='stop')],
                    usage=dict(prompt_tokens=3, completion_tokens=4, total_tokens=7))
            else:
                data = {'error': {'message': 'artificial local error', 'type': 'server_error', 'code': str(status)}}
            payload = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connect = socket.socket.connect
    port = server.server_address[1]
    def local_connect(sock, address):
        if not isinstance(address, tuple) or address[:2] != ('127.0.0.1', port):
            raise AssertionError('non-loopback network forbidden')
        return connect(sock, address)
    try:
        with patch.object(socket.socket, 'connect', local_connect):
            spec = importlib.util.spec_from_file_location('loopback_backend', args.backend)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            client = module.LiteLLMClient.__new__(module.LiteLLMClient)
            client.model, client.base_url = 'openai/artificial', 'http://127.0.0.1:' + str(port) + '/v1'
            client.api_key, client.provider = 'loopback-only-fixture', 'openai'
            params = dict(messages=[{'role': 'user', 'content': 'artificial'}],
                          json_schema=json.dumps({'type': 'object', 'required': ['code']}),
                          function_name='emit', function_description='artificial',
                          model_kwargs=dict(bounded_transport=True, bounded_request_timeout_seconds=5, max_tokens=32))
            async def run():
                for name, status, invalid in [('success', 200, False), ('http429', 429, False),
                                               ('http500', 500, False), ('invalid_schema', 200, True)]:
                    fixture.update(status=status, invalid=invalid)
                    before = len(requests)
                    started = time.monotonic()
                    try:
                        output, usage = await client._query_client(**params)
                        assert name == 'success' and output == {'code': 'print(1)'}
                        assert usage['cost'] is None and usage['total_tokens'] == 7
                    except RuntimeError:
                        assert name != 'success'
                    # This assertion counts actual local HTTP, not a mocked adapter call.
                    assert len(requests) - before == 1, name
                    rows.append(dict(case=name, observed_http_requests=1, elapsed_seconds=time.monotonic()-started))
            asyncio.run(run())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert len(requests) == 4 and all(r['max_tokens'] == 32 for r in requests)
    report = dict(status='LOOPBACK_HTTP_PASS', rows=rows, local_http_requests=len(requests),
                  external_api_calls=0, gpu_requested=False, protected_data_read=False,
                  actual_provider_billing_verified=False,
                  versions={p: importlib.metadata.version(p) for p in ('litellm', 'openai', 'httpx')})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
