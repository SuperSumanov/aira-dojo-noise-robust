"""Bounded kernel-info handshake; no candidate dispatch, retry or kernel restart.

Motivated by four observed readiness failures incorrectly called code timeouts.
Protocol reference: https://github.com/jupyter/jupyter_client/blob/main/jupyter_client/client.py
The reference client repeats kernel_info under a total deadline and checks IOPub.
This implementation is for the existing combined WebSocket message stream.
"""
import math
import time


class KernelReadinessError(RuntimeError):
    """Infrastructure failure; no candidate execution or quality label exists."""


def wait_for_ready(client, timeout_seconds=120., *, clock=time.monotonic, interval=1.):
    if timeout_seconds is None: timeout_seconds=120.
    if (not isinstance(timeout_seconds,(float,int)) or isinstance(timeout_seconds,bool)
            or not math.isfinite(timeout_seconds) or timeout_seconds<=0
            or not isinstance(interval,(float,int)) or not math.isfinite(interval) or interval<=0):
        raise ValueError('positive finite handshake deadline required')
    deadline=clock()+timeout_seconds
    sent=set(); replied=set(); idle=set(); next_send=clock()
    while clock()<deadline:
        current=clock()
        if current>=next_send:
            request=client._send_message(content={},channel='shell',message_type='kernel_info_request')
            if request in sent: raise ValueError('repeated handshake request identity')
            sent.add(request);next_send=current+interval
        remaining=min(deadline,next_send)-clock()
        if remaining<=0:continue
        message=client._receive_message(remaining)
        if clock()>=deadline:return False
        if message is None:continue
        parent=message.get('parent_header',{}).get('msg_id')
        if parent not in sent:continue
        if message.get('msg_type')=='kernel_info_reply':replied.add(parent)
        if message.get('msg_type')=='status' and message.get('content',{}).get('execution_state')=='idle':
            idle.add(parent)
        # Require both channels for the SAME handshake, not stale unrelated traffic.
        if replied & idle:return True
    return False


def classify_readiness_message(lines):
    """For future adapters; old artifacts and running code are never edited."""
    if 'Kernel did not become ready in time.' in '\n'.join(lines):
        return 'kernel_readiness_failure_before_candidate_dispatch'
    return None
