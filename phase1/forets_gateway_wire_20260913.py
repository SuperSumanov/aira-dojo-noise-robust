"""Passive counters on the actual gateway; never changes readiness or retries."""
PAYLOAD = r'''
import json,sys,time
from jupyter_server.services.kernels.connection.channels import ZMQChannelsWebsocketConnection as C
def record(event, **fields):
    try:
        sys.stderr.write('KERNEL_WIRE '+json.dumps(dict(event=event,monotonic_ns=time.monotonic_ns(),**fields),sort_keys=True)+'\n')
        sys.stderr.flush()
    except Exception: pass
incoming,outgoing,connect = C.handle_incoming_message,C._on_zmq_reply,C.connect
def on_incoming(self, raw):
    try:
        msg=json.loads(raw); h=msg.get('header',{})
        if h.get('msg_type')=='kernel_info_request':
            if not hasattr(self,'_wire_ids'): self._wire_ids=set()
            self._wire_ids.add(h.get('msg_id'))
            record('info_ingress',channel=msg.get('channel'),channels_present=bool(self.channels),
                session_matches=h.get('session')==self.session.session)
    except Exception as exc:record('instrumentation_error',error_type=type(exc).__name__)
    return incoming(self,raw)
def on_outgoing(self, stream, msg):
    if isinstance(msg,dict) and msg.get('parent_header',{}).get('msg_id') in getattr(self,'_wire_ids',set()):
        record('info_egress',channel=getattr(stream,'channel',None),message_type=msg.get('msg_type',msg.get('header',{}).get('msg_type')))
    return outgoing(self,stream,msg)
def on_connect(self):
    record('connect')
    future=connect(self)
    if future is not None:
        def done(value):
            record('connect_finished',cancelled=value.cancelled(),
                error_type=type(value.exception()).__name__ if not value.cancelled() and value.exception() else None)
        future.add_done_callback(done)
    return future
C.handle_incoming_message=on_incoming;C._on_zmq_reply=on_outgoing;C.connect=on_connect
record('loaded')
'''

BOOTSTRAP = (
    "import sys,runpy,site; from pathlib import Path; "
    "Path(site.getusersitepackages()).mkdir(parents=True,exist_ok=True); "
    "assert sys.argv[1]=='kernelgateway'; sys.argv.pop(1); "
    "exec(" + repr(PAYLOAD) + "); runpy.run_module('kernel_gateway',run_name='__main__')"
)


def patch_server(text):
    from forets_paid_patch_20260911 import once
    start=text.index('_JUPYTER_BOOTSTRAP = (')
    end=text.index('_SINGULARITY_RUNTIME_ENV_TO_CLEAR = {',start)
    return text[:start]+'from .gateway_wire import BOOTSTRAP as _JUPYTER_BOOTSTRAP\n'+text[end:]
