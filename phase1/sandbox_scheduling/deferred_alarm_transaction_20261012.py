"""Defer Python SIGALRM delivery until the shared-state transaction is unlocked.

Blocking a signal on the main thread alone cannot suppress a Python handler
already queued via another thread. This guard changes neither the deadline nor
the score cutoff. External Slurm/supervisor deadlines remain in force.
"""
import contextlib
import signal
import threading


@contextlib.contextmanager
def defer_alarm():
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError('deadline transaction must run on main thread')
    old = signal.getsignal(signal.SIGALRM)
    pending = []
    def remember(signum, frame):
        pending.append((signum, frame))
    signal.signal(signal.SIGALRM, remember)
    try:
        yield
    finally:
        signal.signal(signal.SIGALRM, old)
        if pending:
            if callable(old):
                old(*pending[0])
            elif old == signal.SIG_DFL:
                signal.raise_signal(signal.SIGALRM)


def protect(transaction):
    @contextlib.contextmanager
    def guarded(*args, **kwargs):
        with defer_alarm():
            with transaction(*args, **kwargs) as state:
                yield state
    return guarded
