"""Same wire requests and accounting, bounded concurrency plus passive timing."""
from forets_paid_patch_20260911 import once


def patch_transport(source):
    source = once(source, 'Serializes wire attempts in each worker to make full-context reservations fit\nequal per-run caps.',
                  'Allows at most four wire attempts per event loop, each atomically reserved\nunder the same run and campaign caps.')
    source = once(source, 'import weakref\n', 'import weakref\nimport time\nimport json\nimport logging\n\n_ACTIVE = weakref.WeakKeyDictionary()\n')
    source = once(source, 'lock = _LOCKS.setdefault(loop, asyncio.Lock())',
                  'lock = _LOCKS.setdefault(loop, asyncio.Semaphore(4))\n    queued = time.monotonic()')
    old = '''        reserve(path, scope, attempt_id)
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
'''
    new = '''        admitted = time.monotonic()
        reserve(path, scope, attempt_id)
        _ACTIVE[loop] = _ACTIVE.get(loop, 0) + 1
        event = dict(attempt_id=attempt_id, concurrency_limit=4,
                     active_at_dispatch=_ACTIVE[loop], queue_wait_seconds=admitted-queued,
                     settled=False)
        wire_start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await asyncio.wait_for(client.post(
                    'https://openrouter.ai/api/v1/chat/completions', json=payload,
                    headers={'Authorization':'Bearer '+kwargs['api_key']}), timeout)
            response.raise_for_status()
            raw = response.json()
            cost = settle(path, attempt_id, raw.get('usage'))
            event['settled'] = True
            result = litellm.ModelResponse(**raw)
            result.usage['cost'] = cost
            return result
        finally:
            event['request_and_settlement_seconds'] = time.monotonic()-wire_start
            _ACTIVE[loop] -= 1
            logging.getLogger(__name__).info('parallel_transport %s', json.dumps(event, sort_keys=True))
'''
    return once(source, old, new)


def patch_readiness(source):
    source = once(source, 'import time\n', 'import time\nimport json\nimport logging\n')
    source = once(source, '    sent=set(); replied=set(); idle=set(); next_send=clock()\n',
        '''    sent=set(); replied=set(); idle=set(); next_send=clock()
    began=clock()
    counts=dict(received=0, foreign_parent=0, shell_reply=0, idle_status=0, other_type=0)
    def finish(success):
        record=dict(counts, success=success, sent=len(sent), matched_reply=len(replied),
                    matched_idle=len(idle), paired=len(replied & idle), elapsed_seconds=clock()-began)
        logging.getLogger(__name__).info('kernel_handshake %s', json.dumps(record, sort_keys=True))
        return success
''')
    source = once(source, 'if clock()>=deadline:return False', 'if clock()>=deadline:return finish(False)')
    source = once(source, '        if parent not in sent:continue\n',
                  "        counts['received']+=1\n        if parent not in sent:\n            counts['foreign_parent']+=1\n            continue\n")
    source = once(source, "        if message.get('msg_type')=='kernel_info_reply':replied.add(parent)\n",
                  "        if message.get('msg_type')=='kernel_info_reply':\n            replied.add(parent);counts['shell_reply']+=1\n")
    source = once(source, '            idle.add(parent)\n', "            idle.add(parent);counts['idle_status']+=1\n        elif message.get('msg_type')!='kernel_info_reply':counts['other_type']+=1\n")
    source = once(source, '        if replied & idle:return True\n    return False\n',
                  '        if replied & idle:return finish(True)\n    return finish(False)\n')
    return source
