"""Opt-in future handshake helper, NOT deployed into any R14 experiment.

Only repeat kernel_info requests, never execute/restart a candidate or kernel.
One monotonic total deadline; unrelated messages cannot extend it. This fixes
a protocol robustness gap, not a demonstrated cause of job17021's timeout.
The caller must ensure no concurrent consumers of the client's message queue.
"""
import math
import time


def wait_for_ready(client, timeout_seconds, *, retry_seconds=1.0,
                   clock=time.monotonic):
    if not (isinstance(timeout_seconds, (int, float)) and
            math.isfinite(timeout_seconds) and timeout_seconds > 0 and
            isinstance(retry_seconds, (int, float)) and
            math.isfinite(retry_seconds) and retry_seconds > 0):
        raise ValueError('finite positive handshake limits required')
    deadline = clock() + timeout_seconds
    next_send = -math.inf
    pending = set()
    while True:
        now = clock()
        if now >= deadline:
            return False
        if now >= next_send:
            message_id = client._send_message(content={}, channel='shell',
                                               message_type='kernel_info_request')
            pending.add(message_id)
            # A slow send must leave a receive window instead of immediately
            # issuing another request. The total deadline is never extended.
            next_send = clock() + retry_seconds
        remaining = min(deadline, next_send) - clock()
        if remaining <= 0:
            continue
        message = client._receive_message(remaining)
        if clock() >= deadline:
            return False
        if not isinstance(message, dict):
            continue
        parent = message.get('parent_header')
        header = message.get('header')
        msg_type = message.get('msg_type')
        if msg_type is None and isinstance(header, dict):
            msg_type = header.get('msg_type')
        if (isinstance(parent, dict) and
                isinstance(parent.get('msg_id'), str) and
                parent['msg_id'] in pending and msg_type == 'kernel_info_reply'):
            return True
