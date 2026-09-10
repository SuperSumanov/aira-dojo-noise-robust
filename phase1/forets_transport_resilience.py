"""Deploy as backends/bounded_retry.py; bounded retries, never provider fallback.

One call to the supplied factory is one separately reserved transport attempt.
Unknown usage/cancellation is retained, not refunded or priced as zero.
"""
import asyncio
import re


def safe_failure(exc, *, response_received):
    """Allowlist numeric status/type only; never stringify an HTTP exception."""
    status = getattr(exc, 'status_code', None)
    if type(status) is not int:
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
    if type(status) is not int or not 100 <= status <= 599:
        status = None
    name = type(exc).__name__
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,79}', name):
        name = 'UnknownError'
    retryable = not response_received and (
        status in (408, 429, 500, 502, 503, 504)
        or (status is None and (isinstance(exc, TimeoutError)
            or name in ('APIConnectionError', 'APITimeoutError', 'ConnectTimeout',
                        'ReadTimeout', 'ConnectError', 'ReadError', 'RemoteProtocolError'))))
    return dict(error_type=name, http_status=status, retryable=retryable)


class BoundedAttemptError(RuntimeError):
    def __init__(self, event):
        self.event = dict(event)
        self.retryable = event['retryable']
        super().__init__('bounded API attempt failed: ' + event['error_type'])


def _sum_known(events, key):
    values = [event.get(key) for event in events]
    if any(type(value) is not int or value < 0 for value in values):
        return None
    return sum(values)


async def query_with_retries(factory, max_attempts, *, sleep=None):
    if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
        raise ValueError('bounded_max_attempts must be an integer in [1, 3]')
    sleep = asyncio.sleep if sleep is None else sleep
    failed = []
    for index in range(max_attempts):
        try:
            output, stats = await factory()
        except BoundedAttemptError as exc:
            failed.append(dict(exc.event))
            if not exc.retryable or index + 1 >= max_attempts:
                raise
            # Fixed backoff uses no search/selector RNG. Worker deadline is outer cap.
            await sleep(2 ** (index + 1))
        else:
            if not failed:
                return output, stats
            stats = dict(stats)
            events = failed + [dict(stats)]
            stats['attempt_history'] = events
            stats['adapter_attempts'] = len(events)
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                stats[key] = _sum_known(events, key)
            stats['cost'] = None
            stats['cost_status'] = 'unpriced'
            stats['token_usage_source'] = 'provider_incomplete' if stats['total_tokens'] is None else 'provider'
            stats['provider_cancellation_verified'] = False
            stats['latency'] = sum(e['latency'] for e in events)
            stats['retry_backoff_seconds'] = sum(2 ** i for i in range(1, len(events)))
            if 'structured_output_requests' in stats:
                stats['structured_output_requests'] = len(events)
            return output, stats
