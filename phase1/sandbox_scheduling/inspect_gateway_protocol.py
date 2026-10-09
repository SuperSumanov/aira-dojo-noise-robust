"""Read installed protocol metadata/source only; no kernel launch/GPU/data."""
import hashlib
import importlib.metadata
import inspect
import json
from jupyter_server.services.kernels.connection.channels import ZMQChannelsWebsocketConnection as C

versions={p:importlib.metadata.version(p) for p in
          ('jupyter-server','jupyter-kernel-gateway','jupyter-client','ipykernel','pyzmq','tornado')}
print(json.dumps({'versions':versions,'source_sha256':hashlib.sha256(inspect.getsource(C).encode()).hexdigest()}))
for name in ('connect','nudge','handle_incoming_message','create_stream','_create_stream','_register_session'):
    obj=getattr(C,name,None)
    if obj is not None:print(name,inspect.getsource(obj))
