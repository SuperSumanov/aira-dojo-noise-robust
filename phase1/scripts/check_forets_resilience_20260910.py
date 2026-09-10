"""Real deployed LiteLLM + SQLite budget + local HTTP, no external API/GPU."""
import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(CUDA_VISIBLE_DEVICES='', PYTHON_DOTENV_DISABLED='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', NO_PROXY='127.0.0.1,localhost',
        LOGGING_DIR=str(args.output.parent), MLE_BENCH_DATA_DIR='/unread', SUPERIMAGE_DIR='/unread',
        DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0, str(args.source/'src'))
    cases = [
        ('transient_recovers', [503, 200], 3, 40, True, 2),
        ('rate_limit_recovers', [429, 200], 3, 40, True, 2),
        ('permanent_auth', [401], 3, 40, False, 1),
        ('permanent_parameter', [400], 3, 40, False, 1),
        ('exhausts_three', [503, 503, 503], 3, 40, False, 3),
        ('budget_stops_retry', [503], 3, 1, False, 1),
        ('default_one_attempt', [503], 1, 40, False, 1),
        ('invalid_response_no_retry', [200], 3, 40, False, 1),
    ]
    requests, rows, current = [], [], {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            index = len(requests) - current['offset'] - 1
            status = current['statuses'][min(index, len(current['statuses']) - 1)]
            if status == 200:
                content = '{}' if current['invalid'] else '{"code":"print(1)"}'
                response = dict(id='local', object='chat.completion', created=1, model='artificial',
                    choices=[dict(index=0, message=dict(role='assistant', content=content), finish_reason='stop')],
                    usage=dict(prompt_tokens=3, completion_tokens=4, total_tokens=7))
            else:
                response = dict(error=dict(message='private-response-must-not-escape', type='server_error', code=str(status)))
            payload = json.dumps(response).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connect = socket.socket.connect
    def local_connect(sock, address):
        if address[:2] != server.server_address:
            raise AssertionError('non-local connection forbidden')
        return connect(sock, address)
    try:
        with patch.object(socket.socket, 'connect', local_connect):
            from dojo.core.solvers.llm_helpers.backends.lite_llm import LiteLLMClient
            from dojo.core.solvers.llm_helpers.backends.run_budget import initialize, RunBudgetError
            from dojo.core.solvers.llm_helpers.backends.bounded_retry import BoundedAttemptError
            client = LiteLLMClient.__new__(LiteLLMClient)
            client.model = 'openai/artificial'
            client.base_url = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
            client.api_key, client.provider = 'local-fixture', 'openai'
            async def exercise():
                for name, statuses, attempts, cap, success, expected_requests in cases:
                    budget = Path(tempfile.mkdtemp(prefix='forets-retry-test-'))/'attempts.sqlite'
                    initialize(budget, cap, 32)
                    os.environ['FORETS_RUN_BUDGET_PATH'] = str(budget)
                    current.update(statuses=statuses, offset=len(requests), invalid=name=='invalid_response_no_retry')
                    try:
                        _, stats = await client._query_client(messages=[dict(role='user', content='public fixture')],
                            json_schema=json.dumps(dict(type='object', required=['code'])),
                            function_name='emit', function_description='fixture',
                            model_kwargs=dict(bounded_transport=True, bounded_request_timeout_seconds=5,
                                              bounded_max_attempts=attempts, max_tokens=32))
                        assert success, name
                        if expected_requests > 1:
                            assert stats['adapter_attempts'] == expected_requests and stats['total_tokens'] is None
                    except (BoundedAttemptError, RunBudgetError) as exc:
                        assert not success, name
                        assert 'private-response' not in str(exc)
                        if isinstance(exc, BoundedAttemptError) and statuses[0] != 200:
                            assert exc.event['http_status'] == statuses[-1]
                    with sqlite3.connect(budget.as_uri()+'?mode=ro', uri=True) as db:
                        reserved = db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]
                    actual = len(requests) - current['offset']
                    assert actual == reserved == expected_requests, (name, actual, reserved)
                    rows.append(dict(case=name, observed_http_requests=actual, reserved=reserved))
            asyncio.run(exercise())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    report = dict(status='PASS', cases=rows, cases_passed=len(rows),
                  external_api_calls=0, gpu_jobs=0, protected_data_read=False)
    with args.output.open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(report))


if __name__ == '__main__': main()
