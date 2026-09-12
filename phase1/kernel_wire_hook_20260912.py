"""Diagnostic-only gateway hooks: log message kinds and matching, never payloads."""
import json
import os
from pathlib import Path
import sys
import time

from jupyter_server.services.kernels.connection.channels import ZMQChannelsWebsocketConnection as Connection

PATH = Path(os.environ.get('KERNEL_DIAG_LOG', '/workspace/kernel-wire.jsonl'))


def record(event, **fields):
    row = dict(event=event, trial=int(os.environ['KERNEL_DIAG_TRIAL']), monotonic_ns=time.monotonic_ns(), **fields)
    try:
        with PATH.open('a') as stream:
            stream.write(json.dumps(row, sort_keys=True)+'\n')
    except OSError:
        # Logging failure must not become a fabricated channel failure.
        sys.stderr.write('KERNEL_WIRE_TRACE_WRITE_FAILURE\n')


incoming = Connection.handle_incoming_message
outgoing = Connection._on_zmq_reply
connect = Connection.connect


def on_incoming(self, raw):
    try:
        msg = json.loads(raw)
        header = msg.get('header', {})
        if not hasattr(self, '_diagnostic_ids'):
            self._diagnostic_ids = set()
        self._diagnostic_ids.add(header.get('msg_id'))
        record('server_incoming', channel=msg.get('channel'), message_type=header.get('msg_type'),
               session_matches=header.get('session') == self.session.session)
    except Exception as exc:
        record('instrumentation_error', error_type=type(exc).__name__)
    return incoming(self, raw)


def on_outgoing(self, stream, msg):
    # Legacy JSON websocket receives an already verified dict here. Never
    # deserialize it a second time: Session's replay protection has side effects.
    if isinstance(msg, dict):
        record('server_outgoing', channel=getattr(stream, 'channel', None),
               message_type=msg.get('msg_type', msg.get('header', {}).get('msg_type')),
               parent_matches=msg.get('parent_header', {}).get('msg_id') in getattr(self, '_diagnostic_ids', set()))
    return outgoing(self, stream, msg)


def on_connect(self):
    record('server_connect')
    future = connect(self)
    if future is not None:
        def done(value):
            record('server_connect_finished', cancelled=value.cancelled(),
                   exception_type=type(value.exception()).__name__ if not value.cancelled() and value.exception() else None)
        future.add_done_callback(done)
    return future


Connection.handle_incoming_message = on_incoming
Connection._on_zmq_reply = on_outgoing
Connection.connect = on_connect
record('instrumentation_loaded')
