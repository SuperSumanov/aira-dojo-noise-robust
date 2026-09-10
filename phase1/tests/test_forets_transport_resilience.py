import asyncio
from types import SimpleNamespace as NS

import pytest

from phase1.forets_transport_resilience import BoundedAttemptError, query_with_retries, safe_failure


class APIError(Exception):
    def __init__(self, status):
        self.status_code = status
    def __str__(self):
        raise AssertionError('provider text must not be accessed')


@pytest.mark.parametrize('status,retryable', [(400, False), (401, False), (402, False),
    (403, False), (404, False), (408, True), (429, True), (500, True),
    (502, True), (503, True), (504, True), (None, False), ('503', False), (True, False)])
def test_status_allowlist(status, retryable):
    event = safe_failure(APIError(status), response_received=False)
    assert event['retryable'] is retryable
    assert event['http_status'] == (status if type(status) is int else None)
    assert not safe_failure(APIError(status), response_received=True)['retryable']


def test_response_status_fallback_and_timeout():
    exc = APIError(None)
    exc.response = NS(status_code=503)
    assert safe_failure(exc, response_received=False)['http_status'] == 503
    assert safe_failure(TimeoutError(), response_received=False)['retryable']


def event():
    return dict(safe_failure(APIError(503), response_received=False), latency=0.1,
                cost=None, prompt_tokens=None, completion_tokens=None)


def test_retry_recovery_keeps_failed_cost_and_backoff():
    calls, delays = [], []
    async def factory():
        calls.append(len(calls))
        if len(calls) < 3:
            raise BoundedAttemptError(event())
        return 'ok', dict(latency=.2, prompt_tokens=3, completion_tokens=4,
                          total_tokens=7, structured_output_requests=1)
    async def sleep(delay):
        delays.append(delay)
    output, stats = asyncio.run(query_with_retries(factory, 3, sleep=sleep))
    assert output == 'ok' and len(calls) == 3 and delays == [2, 4]
    assert stats['adapter_attempts'] == stats['structured_output_requests'] == 3
    assert stats['total_tokens'] is None and stats['cost'] is None
    assert len(stats['attempt_history']) == 3 and stats['retry_backoff_seconds'] == 6


@pytest.mark.parametrize('attempts', [1, 2, 3])
def test_retry_exhaustion(attempts):
    calls = []
    async def factory():
        calls.append(1)
        raise BoundedAttemptError(event())
    async def sleep(_): pass
    with pytest.raises(BoundedAttemptError):
        asyncio.run(query_with_retries(factory, attempts, sleep=sleep))
    assert len(calls) == attempts


@pytest.mark.parametrize('error', [asyncio.CancelledError(), ValueError('bad config'),
    BoundedAttemptError(dict(event(), retryable=False))])
def test_nonretryable_and_cancellation_propagate(error):
    calls = []
    async def factory():
        calls.append(1)
        raise error
    with pytest.raises(type(error)):
        asyncio.run(query_with_retries(factory, 3))
    assert calls == [1]


@pytest.mark.parametrize('invalid', [0, 4, True, 2.0, '3'])
def test_invalid_limit_no_dispatch(invalid):
    async def factory(): raise AssertionError('dispatched')
    with pytest.raises(ValueError):
        asyncio.run(query_with_retries(factory, invalid))


def test_failed_sibling_does_not_cancel_other_slots_or_accept_partial_pool():
    import ast
    from phase1.forets_resilience_patch import revised, BATCH
    tree = ast.parse(revised()[BATCH])
    gather = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'gather')
    completed = []
    async def obtain(slot):
        if slot == 0:
            raise BoundedAttemptError(event())
        await asyncio.sleep(.01)
        completed.append(slot)
        return 'candidate'
    namespace = dict(asyncio=asyncio, count=4, obtain=obtain)
    exec(compile(ast.Module(body=[gather], type_ignores=[]), 'actual-patched-gather', 'exec'), namespace)
    with pytest.raises(BoundedAttemptError):
        asyncio.run(namespace['gather']())
    assert sorted(completed) == [1, 2, 3]
