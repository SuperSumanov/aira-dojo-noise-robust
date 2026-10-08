"""Common timing/cleanup adapter for both R14 live admission arms.

Native MCTS and operators are unchanged. Preview and each task action remain
sequential within a run. Queue delay is charged to the outer run deadline but
removed from the execution-duration field sent back to the native agent.
"""
import contextlib
import hashlib
import inspect
import math
import time
from pathlib import Path
from bounded_readiness import wait_for_ready
from live_admission import Lease, append_event

CLIENT_SHA = 'a6c6abdca37745ce8d5137f48595a3c0e6332c113e8133b0782425b7bbb291bf'
HELPER_SHA = '0fd8ead4c8eac2fc128b36d096ed15ceebeabc43a5fc5841d8c17e882ca381cd'


def corrected_seconds(elapsed, wait):
    if not math.isfinite(elapsed) or not math.isfinite(wait) or elapsed < 0 or wait < 0 or elapsed + 1e-6 < wait:
        raise ValueError('execution/queue timing inconsistency')
    return max(0., elapsed-wait)


def install(row, ep, deadline):
    from dojo.core.interpreters.jupyter import jupyter_client as client
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.tasks.mlebench.task import MLEBenchTask

    def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if sha(client.__file__) != CLIENT_SHA or sha(Path(__file__).with_name('bounded_readiness.py')) != HELPER_SHA:
        raise ValueError('runtime handshake pin drift')
    current = [None]
    counters = dict(operation=0, generation=0)
    event_file = ep/'events.jsonl'

    def record(event, **kw):
        append_event(event_file, dict(time=time.time(), event=event, run=row['index'],
                     elapsed=deadline.elapsed(), **kw))

    @contextlib.contextmanager
    def operation(kind, state):
        if current[0] is not None:
            raise ValueError('nested run operation')
        ordinal = counters['operation'];counters['operation'] += 1
        key = f"{row['index']}:{ordinal}"
        lease = Lease(ep.parent/f"queue-{row['block']}", key, deadline.check,
                      lambda event, **kw:record(event, operation=ordinal, kind=kind, **kw))
        current[0] = lease
        record('operation_ready', operation=ordinal, kind=kind)
        try:
            yield
        finally:
            # Native successful task.step_task already closes its factory. This
            # also closes a preview-only kernel and exceptions before release.
            cleaned = False
            try:
                state['solver_interpreter'].close()
                cleaned = True
            finally:
                record('cleanup', operation=ordinal, kind=kind, verified=cleaned)
                if cleaned:
                    lease.release(cleanup_verified=True)
                current[0] = None

    original_step = MLEBenchTask.step_task
    def step(self, state, action):
        with operation('candidate', state):
            return original_step(self, state, action)
    MLEBenchTask.step_task = step

    original_preview = MCTS.update_data_preview
    def preview(self, state):
        with operation('preview', state):
            return original_preview(self, state)
    MCTS.update_data_preview = preview

    original_execute = client.JupyterKernelClient.execute
    def execute(self, *args, **kwargs):
        lease = current[0]
        if lease is None:
            raise ValueError('unscoped interpreter execution')
        lease.acquire()
        return original_execute(self, *args, **kwargs)
    client.JupyterKernelClient.execute = execute

    def ready(self, timeout_seconds=None):
        begin=time.monotonic()
        ok=wait_for_ready(self,120 if timeout_seconds is None else timeout_seconds)
        record('kernel_ready',success=ok,seconds=time.monotonic()-begin)
        return ok
    client.JupyterKernelClient.wait_for_ready = ready

    original_code = JupyterCodeExecutor.execute_code
    def execute_code(self, *args, **kwargs):
        lease=current[0]
        before=0. if lease is None else lease.wait_seconds
        result=original_code(self,*args,**kwargs)
        extra=0. if lease is None else lease.wait_seconds-before
        result.exec_time=corrected_seconds(result.exec_time,extra)
        record('cell_return',queue_seconds=extra,exec_seconds=result.exec_time,
               exit_code=result.exit_code,timed_out=result.timed_out)
        return result
    JupyterCodeExecutor.execute_code = execute_code

    original_call=GenericLLM.__call__
    def begin_call():
        if current[0] is not None:
            raise ValueError('generation inside an execution lease')
        n=counters['generation'];counters['generation']+=1
        record('generation_started',call=n)
        return n,time.monotonic()
    if inspect.iscoroutinefunction(original_call):
        async def call(self,*args,**kwargs):
            n,start=begin_call();success=False
            try:
                value=await original_call(self,*args,**kwargs);success=True;return value
            finally:record('generation_returned',call=n,success=success,seconds=time.monotonic()-start)
    else:
        def call(self,*args,**kwargs):
            n,start=begin_call();success=False
            try:
                value=original_call(self,*args,**kwargs);success=True;return value
            finally:record('generation_returned',call=n,success=success,seconds=time.monotonic()-start)
    GenericLLM.__call__=call
    record('runtime_hooks_installed',native_policy_unchanged=True)
