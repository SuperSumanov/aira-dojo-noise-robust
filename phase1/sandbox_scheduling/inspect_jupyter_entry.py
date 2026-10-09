"""Read-only CLI process-boundary audit; never launches a kernel or subprocess."""
import hashlib
import inspect
import json

from jupyter_core import command
from kernel_gateway.gatewayapp import KernelGatewayApp

sources = {name: inspect.getsource(getattr(command, name))
           for name in ('main', '_execvp')}
print(json.dumps({
    'source_sha256': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in sources.items()},
    'direct_gateway_entry_available': callable(KernelGatewayApp.launch_instance),
    'no_kernel_or_subprocess_launched': True,
}))
for name, source in sources.items():
    print(name, source)
