"""Private task-call receipts, not full cost accounting or checkpoint recovery.

The caller's task and interpreter are unchanged. Wall time includes whatever the
task actually does (execution, fetching and grading); interpreter-reported time
is kept separately and is not assumed to include startup or cleanup. No scores,
terminal output, labels or exception messages enter these receipts.
"""
import hashlib
import math
import re
import time
from datetime import datetime, timezone


class ExecutionWitnessError(RuntimeError):
    pass


SECRET = re.compile(r'sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|'
                    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class ExecutionWitness:
    def __init__(self, ledger, task, max_calls, execution_timeout, output_key,
                 clock_ns=time.monotonic_ns):
        if type(max_calls) is not int or max_calls <= 0:
            raise ExecutionWitnessError('positive execution-call cap required')
        if not finite_nonnegative(execution_timeout) or execution_timeout <= 0:
            raise ExecutionWitnessError('finite positive configured execution timeout required')
        self.ledger, self.task = ledger, task
        self.max_calls, self.timeout = max_calls, execution_timeout
        self.output_key, self.clock_ns = output_key, clock_ns

    def task_for(self, slot, role):
        if role not in {'candidate', 'debug'}:
            raise ExecutionWitnessError('invalid execution role')
        return _TaskProxy(self, slot, role)

    def call(self, slot, role, state, action):
        if not isinstance(action, str) or not action.strip() or SECRET.search(action):
            raise ExecutionWitnessError('execution code security/schema gate')
        interpreter = state['solver_interpreter']
        runtime_timeout = getattr(interpreter, 'timeout', None)
        if (not finite_nonnegative(runtime_timeout) or runtime_timeout != self.timeout):
            raise ExecutionWitnessError('runtime and configured execution timeout mismatch')
        # These are observed attributes, not evidence of physical GPU allocation,
        # model/evaluator identity, sandbox isolation, or a hard wall-clock bound.
        runtime = dict(interpreter_class=type(interpreter).__module__ + '.' + type(interpreter).__qualname__,
                       execution_timeout=runtime_timeout)
        intent = dict(role=role, code=action,
                      code_sha256=hashlib.sha256(action.encode()).hexdigest(),
                      runtime=runtime, utc_intent=datetime.now(timezone.utc).isoformat())
        call_id = self.ledger.begin_task_call(slot, intent, self.max_calls)
        start = self.clock_ns()  # After durable intent, before the real task call.
        try:
            result = self.task.step_task(state, action)
        except BaseException as exc:
            elapsed = self.clock_ns() - start
            self.ledger.finish_task_call(call_id, 'raised', elapsed, None, type(exc).__name__)
            raise
        elapsed = self.clock_ns() - start
        try:
            if not isinstance(result, tuple) or len(result) != 2 or not isinstance(result[1], dict):
                raise ExecutionWitnessError('invalid task return shape')
            output = result[1][self.output_key]
            exit_code, timed_out, exec_time = output.exit_code, output.timed_out, output.exec_time
            if (exit_code is not None and type(exit_code) is not int or
                    type(timed_out) is not bool or not finite_nonnegative(exec_time)):
                raise ExecutionWitnessError('invalid execution metadata')
            metadata = dict(exit_code_reported=exit_code, timed_out_reported=timed_out,
                            exec_time_reported_seconds=exec_time)
        except (ExecutionWitnessError, KeyError, AttributeError, TypeError):
            self.ledger.finish_task_call(call_id, 'invalid_return', elapsed, None, None)
            raise ExecutionWitnessError('task returned without valid execution metadata') from None
        # This commit precedes analysis, journal mutation and further debug calls.
        self.ledger.finish_task_call(call_id, 'returned', elapsed, metadata, None)
        return result  # Preserve the task's actual state/result objects and values.


class _TaskProxy:
    def __init__(self, witness, slot, role):
        self._witness, self._slot, self._role = witness, slot, role

    def __getattr__(self, name):
        return getattr(self._witness.task, name)

    def step_task(self, state, action):
        return self._witness.call(self._slot, self._role, state, action)
