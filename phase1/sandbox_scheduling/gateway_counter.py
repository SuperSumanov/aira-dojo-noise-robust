"""Diagnostic-only counters in empty-kernel gateway; no message values saved."""
import atexit
from collections import Counter
import json
from pathlib import Path
import runpy
import site

Path(site.getusersitepackages()).mkdir(parents=True,exist_ok=True)
from jupyter_server.services.kernels.connection.channels import ZMQChannelsWebsocketConnection as C

counts=Counter()
DEST=Path('/workspace/gateway-counts.json')
TYPES={'kernel_info_request','kernel_info_reply','status','execute_request','execute_reply','error'}


def persist():
    # Counts only. This extra I/O means the diagnostic is not a timing comparison.
    DEST.write_text(json.dumps(dict(counts),sort_keys=True),encoding='utf-8')


def record(key):
    counts[key]+=1;persist()


def message_kind(message):
    try:
        if isinstance(message,str):message=json.loads(message)
        elif isinstance(message,list):
            # Read header only. Do not call Session.deserialize: it mutates the
            # duplicate-signature history and would corrupt the original path.
            position=message.index(b'<IDS|MSG>')
            message={'header':json.loads(message[position+2])}
        kind=message.get('header',{}).get('msg_type',message.get('msg_type'))
        return kind if kind in TYPES else 'other'
    except (ValueError,TypeError,AttributeError,IndexError):return 'unknown'


original_incoming=C.handle_incoming_message
def incoming(self,message):
    record('incoming_'+message_kind(message))
    result=original_incoming(self,message)
    record('incoming_forwarded')
    return result
C.handle_incoming_message=incoming

original_outgoing=C.handle_outgoing_message
def outgoing(self,stream,message):
    record('outgoing_'+message_kind(message))
    result=original_outgoing(self,stream,message)
    record('outgoing_forwarded')
    return result
C.handle_outgoing_message=outgoing

original_nudge=C.nudge
def nudge(self):
    record('nudge_enter')
    state=getattr(self.kernel_manager,'execution_state',None)
    record('nudge_state_'+(state if state in ('starting','busy','idle','dead') else 'other'))
    future=original_nudge(self)
    def finished(f):
        record('nudge_cancelled' if f.cancelled() else 'nudge_failed' if f.exception() else 'nudge_done')
    future.add_done_callback(finished)
    return future
C.nudge=nudge

atexit.register(persist)
if __name__=='__main__':runpy.run_module('jupyter',run_name='__main__')
