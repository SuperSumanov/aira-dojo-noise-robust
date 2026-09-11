"""OpenRouter-only paid transport, used INSIDE the existing strict tool parser.

Serializes wire attempts in each worker to make full-context reservations fit
equal per-run caps. Both arms use this same explicit successor protocol.
No redirects, SDK retries, model/provider fallback, attachments or plugins.
"""
import asyncio
import os
import weakref

try:
    from .paid_budget import MODEL, PROVIDER, reserve, settle, BudgetStopped
except ImportError:
    from forets_paid_budget_20260911 import MODEL, PROVIDER, reserve, settle, BudgetStopped

_LOCKS = weakref.WeakKeyDictionary()


def payload_for(messages, kwargs):
    if (kwargs.get('model') != 'openai/'+MODEL
            or kwargs.get('base_url') != 'https://openrouter.ai/api/v1'
            or kwargs.get('extra_body') != {'provider': PROVIDER}
            or kwargs.get('max_tokens') != 8192):
        raise BudgetStopped('paid route/config mismatch')
    allowed = {'model','base_url','api_key','extra_body','max_tokens','temperature','top_p',
               'max_retries','num_retries','request_timeout','tools','tool_choice','response_format','seed'}
    if set(kwargs) - allowed:
        raise BudgetStopped('unpriced extra request option')
    if not isinstance(messages, list) or not messages:
        raise BudgetStopped('text messages required')
    for message in messages:
        if (set(message) - {'role','content'} or not isinstance(message.get('content'),str)
                or message.get('role') not in ('system','user','assistant')):
            raise BudgetStopped('no attachments, cache directives or auxiliary billing')
    payload = {k:v for k,v in kwargs.items() if k in
               ('max_tokens','temperature','top_p','tools','tool_choice','response_format','seed')}
    payload.update(model=MODEL, messages=messages, provider=PROVIDER, stream=False)
    return payload


async def complete(messages, kwargs, timeout, attempt_id):
    import httpx
    import litellm
    payload = payload_for(messages, kwargs)
    path, scope = os.environ.get('FORETS_PAID_LEDGER'), os.environ.get('FORETS_PAID_SCOPE')
    if not path or not scope or not kwargs.get('api_key'):
        raise BudgetStopped('paid ledger, scope and remote credential required')
    loop = asyncio.get_running_loop()
    lock = _LOCKS.setdefault(loop, asyncio.Lock())
    # The wait is covered by the existing worker wall limit, not billed as an
    # API timeout. timeout starts only after a reservation and wire dispatch.
    async with lock:
        reserve(path, scope, attempt_id)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await asyncio.wait_for(client.post(
                'https://openrouter.ai/api/v1/chat/completions', json=payload,
                headers={'Authorization':'Bearer '+kwargs['api_key']}), timeout)
        # Every non-2xx response remains unresolved; never parse/print raw errors.
        response.raise_for_status()
        raw = response.json()
        cost = settle(path, attempt_id, raw.get('usage'))
        result = litellm.ModelResponse(**raw)
        # Preserve the authoritative upstream charge, not LiteLLM estimates.
        result.usage['cost'] = cost
        return result
