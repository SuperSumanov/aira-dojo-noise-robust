"""Opt-in ForeTS logical-request audit; not a provider billing or sandbox proof."""
import copy
import hashlib
import json
import random
import re
from contextlib import contextmanager
from contextvars import ContextVar

ACTIVE = ContextVar('forets_request_guard', default=None)
CREDENTIAL = re.compile(r'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def package_order(packages):
    if ACTIVE.get() is None:
        # Preserve upstream default semantics outside the explicitly audited batch.
        random.shuffle(packages)
        return packages
    # The same configured order for all candidates/retries; never mutate config.
    return list(packages)


class BatchRequestGuard:
    def __init__(self, ledger, max_calls):
        if type(max_calls) is not int or max_calls <= 0:
            raise ValueError('positive logical-call cap required')
        self.ledger, self.max_calls = ledger, max_calls

    @contextmanager
    def slot(self, slot):
        if ACTIVE.get() is not None:
            raise RuntimeError('nested request guard')
        token = ACTIVE.set((self, slot))
        try:
            yield
        finally:
            ACTIVE.reset(token)


async def audited_query(client, messages, **kwargs):
    ctx = ACTIVE.get()
    if ctx is None:
        return await client.query(messages, **kwargs)
    guard, slot = ctx
    # Copy both sides: transport mutation must not alter a retained request snapshot.
    request = copy.deepcopy(dict(messages=messages, kwargs=kwargs,
                                client_class=type(client).__module__ + '.' + type(client).__qualname__))
    request_hash = fingerprint(request)  # Reject unserializable/nonfinite requests before dispatch.
    if CREDENTIAL.search(json.dumps(request, sort_keys=True, allow_nan=False)):
        raise RuntimeError('credential-shaped request blocked before storage or dispatch')
    call_id = guard.ledger.begin_llm_request(slot, request_hash, request, guard.max_calls)
    outgoing = copy.deepcopy(request)
    try:
        output, usage = await client.query(outgoing['messages'], **outgoing['kwargs'])
    except BaseException as exc:
        # Request may have reached the server. Unknown usage is not free; never retry it here.
        guard.ledger.finish_llm_request(call_id, 'ambiguous', None, type(exc).__name__)
        raise
    # Do not silently retry billing / account for a malformed return as zero usage.
    try:
        frozen_usage = copy.deepcopy(usage)
        fingerprint(frozen_usage)
    except Exception:
        guard.ledger.finish_llm_request(call_id, 'invalid_usage', None, 'UnserializableUsage')
        raise RuntimeError('provider usage cannot be audited') from None
    guard.ledger.finish_llm_request(call_id, 'returned', frozen_usage, None)
    if fingerprint(outgoing) != request_hash:
        raise RuntimeError('client mutated dispatched request; no automatic retry')
    return output, usage
