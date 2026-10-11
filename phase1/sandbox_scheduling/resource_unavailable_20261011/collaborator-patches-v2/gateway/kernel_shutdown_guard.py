"""Bound a restart/shutdown race in the pinned Jupyter client 8.9.1 gateway.

Automatic restart replaces km.ready without adding an MKM pending entry. The
original shutdown calls ready.exception() while it is unfinished (InvalidState).
Wait for that state transition, not for a user program; never replay execution.
This is an experimental overlay, not a package/image upgrade or production edit.
"""
import asyncio,hashlib,inspect,json,textwrap
from pathlib import Path

METHOD_SHA='aaaee97aa5b9c52ae47c68f8503468153da8d2a6f0b8bd0756f55e5b14bb6c7e'
ANCHOR='        # If a pending kernel raised an exception, remove it.\n'
INSERT='''        # Autorestart may leave ready pending without an MKM pending task.
        await _r14_wait_ready_transition(km)
'''

async def wait_ready_transition(km,timeout=15.0):
    deadline=asyncio.get_running_loop().time()+timeout
    while not km.ready.done():
        remaining=deadline-asyncio.get_running_loop().time()
        if remaining<=0:
            raise TimeoutError('Kernel lifecycle transition did not settle before shutdown')
        done,_=await asyncio.wait((km.ready,),timeout=remaining)
        if not done:
            raise TimeoutError('Kernel lifecycle transition did not settle before shutdown')
    # Do not swallow or retrieve a failed future here. The unchanged caller
    # handles exceptional/cancelled ready states, as it did before the overlay.

def overlay_method(source):
    if source.count(ANCHOR)!=1:raise ValueError('shutdown interface drift')
    value=source.replace(ANCHOR,INSERT+ANCHOR,1)
    compile(textwrap.dedent(value),'pinned-shutdown-guard','exec')
    return value

def install():
    from jupyter_client.multikernelmanager import MultiKernelManager as cls,AsyncMultiKernelManager as ac
    from jupyter_client.utils import run_sync
    original=cls._async_shutdown_kernel
    source=inspect.getsource(original)
    assert hashlib.sha256(source.encode()).hexdigest()==METHOD_SHA
    assert ac.shutdown_kernel is original
    scope=dict(original.__globals__,_r14_wait_ready_transition=wait_ready_transition)
    exec(compile(textwrap.dedent(overlay_method(source)),'pinned-shutdown-guard','exec'),scope)
    fixed=scope['_async_shutdown_kernel']
    cls._async_shutdown_kernel=fixed
    cls.shutdown_kernel=run_sync(fixed)
    ac.shutdown_kernel=fixed
    # Fresh receipt for every gateway launch, including a reused workspace.
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', prefix='kernel-shutdown-guard-installed-',
                                     suffix='.json', dir='/workspace', delete=False) as f:
        json.dump(dict(original_sha256=METHOD_SHA,transition_timeout=15,no_candidate_retry=True),f)

if __name__!='__main__':
    import os,sys
    if os.path.basename(sys.argv[0])=='jupyter-kernelgateway':install()
