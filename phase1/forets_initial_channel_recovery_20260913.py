"""At most one same-kernel channel replacement, before any candidate dispatch.

This is a bounded transport mitigation, not proof of the intermittent cause.
The existing paired reply+idle readiness test and the 120-second total remain.
"""
import json
import logging
import math
import time


def ready_before_first_dispatch(executor, *, clock=time.monotonic, first_seconds=10.):
    total=executor._wait_timeout
    if type(total) not in (float,int) or not math.isfinite(total) or total<=0:
        raise ValueError('finite positive readiness budget')
    if type(first_seconds) not in (float,int) or not 0<first_seconds<=total:
        raise ValueError('bounded initial phase')
    start=clock();deadline=start+total
    first=min(first_seconds,total) if not executor._candidate_dispatched else total
    if executor._jupyter_kernel_client.wait_for_ready(timeout_seconds=first):return True
    if executor._candidate_dispatched or clock()>=deadline:return False
    # No kernel restart/delete/create, and no candidate or fetch execution here.
    executor._jupyter_kernel_client.stop()
    remaining=deadline-clock()
    if remaining<=0:return False
    fresh=executor._jupyter_client.get_kernel_client(executor._kernel_id,connection_timeout=min(10.,remaining))
    executor._jupyter_kernel_client=fresh
    remaining=deadline-clock()
    ready=remaining>0 and fresh.wait_for_ready(timeout_seconds=remaining)
    logging.getLogger(__name__).info('initial_channel_recovery %s',json.dumps(dict(
        recovered=bool(ready),same_kernel=True,prior_candidate_dispatch=False,
        elapsed_seconds=clock()-start,maximum_replacements=1),sort_keys=True))
    return bool(ready) and clock()<deadline


def patch_sources(client,executor):
    def once(text,old,new):
        if text.count(old)!=1:raise ValueError('exact production patch site')
        return text.replace(old,new,1)
    client=once(client,'def get_kernel_client(self, kernel_id: str) -> JupyterKernelClient:',
        'def get_kernel_client(self, kernel_id: str, *, connection_timeout: float = 300.) -> JupyterKernelClient:')
    client=once(client,'return JupyterKernelClient(ws_url, headers)',
        'return JupyterKernelClient(ws_url, headers, connection_timeout=connection_timeout)')
    client=once(client,'def __init__(self, url: str, headers: dict[str, str]):',
        'def __init__(self, url: str, headers: dict[str, str], *, connection_timeout: float = 300.):')
    client=once(client,'        self._connected_event.wait(timeout=self._time_cycle)',
        '        if not self._connected_event.wait(timeout=connection_timeout):\n'
        '            self.stop()\n'
        '            raise TimeoutError("Jupyter channel connection deadline")')
    executor=once(executor,'        self._wait_timeout = 120',
        '        self._wait_timeout = 120\n        self._candidate_dispatched = False')
    old='        ready = self._jupyter_kernel_client.wait_for_ready(timeout_seconds=self._wait_timeout)'
    # The fetch path is deliberately unchanged. The first site is execute_code.
    if executor.count(old)!=2:raise ValueError('execute and fetch readiness sites')
    executor=executor.replace(old,
        '        from .initial_channel_recovery import ready_before_first_dispatch\n'
        '        ready = ready_before_first_dispatch(self)',1)
    executor=once(executor,'        result = self._jupyter_kernel_client.execute(code, timeout_seconds=self._timeout)',
        '        self._candidate_dispatched = True\n'
        '        result = self._jupyter_kernel_client.execute(code, timeout_seconds=self._timeout)')
    return client,executor
