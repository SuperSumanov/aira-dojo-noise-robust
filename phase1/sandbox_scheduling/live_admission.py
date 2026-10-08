"""FIFO admission after kernel readiness; not a search or candidate selector.

The directory is private to the trusted host controller, never container-bound.
No automatic lease expiry: release is legal only after owned kernel cleanup.
"""
import contextlib
import json
import os
import signal
from pathlib import Path
import threading
import time


class AdmissionState:
    def __init__(self, limit, queue=None, active=None, finished=None):
        if limit not in (1, 2):
            raise ValueError('fixed admission width')
        self.limit = limit
        self.queue = list(queue or [])
        self.active = list(active or [])
        self.finished = list(finished or [])
        ids = self.queue + self.active + self.finished
        if len(ids) != len(set(ids)) or len(self.active) > limit:
            raise ValueError('invalid lease state')

    def request(self, key):
        if key in self.queue + self.active + self.finished:
            raise ValueError('duplicate request')
        self.queue.append(key)

    def admit(self, key):
        if self.queue and self.queue[0] == key and len(self.active) < self.limit:
            self.queue.pop(0)
            self.active.append(key)
            return True
        return False

    def finish(self, key, *, cleanup_verified):
        if not cleanup_verified or key not in self.active:
            raise ValueError('unsafe or unknown release')
        self.active.remove(key)
        self.finished.append(key)

    def cancel_waiting(self, key):
        if key not in self.queue:
            raise ValueError('cannot cancel an active lease')
        self.queue.remove(key)
        self.finished.append(key)

    def value(self):
        return dict(limit=self.limit, queue=self.queue, active=self.active, finished=self.finished)


def append_event(path, value):
    raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        if os.write(fd, raw) != len(raw):
            raise OSError('short event write')
    finally:
        os.close(fd)


def initialize(directory, limit):
    directory = Path(directory)
    directory.mkdir(mode=0o700, exist_ok=False)
    with (directory/'state.json').open('x') as f:
        json.dump(AdmissionState(limit).value(), f)
    (directory/'mutex').touch(exist_ok=False)


@contextlib.contextmanager
def locked(directory):
    import fcntl
    directory = Path(directory)
    with (directory/'mutex').open('r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM})
        try:
            state = AdmissionState(**json.loads((directory/'state.json').read_text()))
            yield state
            target = directory/f'state-{os.getpid()}-{threading.get_ident()}.tmp'
            with target.open('x') as f:
                json.dump(state.value(), f, allow_nan=False)
            os.replace(target, directory/'state.json')
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)


class Lease:
    def __init__(self, directory, key, check_deadline, record):
        self.directory = Path(directory)
        self.key = key
        self.check_deadline = check_deadline
        self.record = record
        self.held = False
        self.wait_seconds = 0.0

    def _event(self, kind, state):
        append_event(self.directory/'events.jsonl', dict(event=kind, key=self.key, time=time.time(),
                     queued=len(state.queue), active=len(state.active), limit=state.limit))

    def acquire(self):
        if self.held:
            return
        start = time.monotonic()
        try:
            with locked(self.directory) as state:
                state.request(self.key)
                self._event('queued', state)
            while True:
                self.check_deadline()
                with locked(self.directory) as state:
                    if state.admit(self.key):
                        self.held = True
                        self.wait_seconds = time.monotonic()-start
                        self._event('admitted', state)
                        break
                time.sleep(.05)
        except BaseException:
            # A deadline may be delivered immediately after an atomic commit.
            # Consult persisted state, never infer lease ownership from timing.
            with locked(self.directory) as state:
                self.held = self.key in state.active
                if self.key in state.queue:
                    state.cancel_waiting(self.key)
                    self._event('queue_cancelled', state)
            self.wait_seconds = time.monotonic()-start
            self.record('admission_interrupted',wait_seconds=self.wait_seconds,held=self.held)
            raise
        self.record('admitted', wait_seconds=self.wait_seconds)

    def release(self, *, cleanup_verified):
        if not self.held:
            return
        with locked(self.directory) as state:
            state.finish(self.key, cleanup_verified=cleanup_verified)
            self._event('released', state)
        self.held = False
        self.record('released')


def audit_events(events, limit):
    state = AdmissionState(limit)
    admissions = releases = cancelled = peak = 0
    for event in events:
        key, kind = event['key'], event['event']
        if kind == 'queued':
            state.request(key)
        elif kind == 'admitted':
            if not state.admit(key):
                raise ValueError('non-FIFO or over-capacity admission')
            admissions += 1
        elif kind == 'released':
            state.finish(key, cleanup_verified=True)
            releases += 1
        elif kind == 'queue_cancelled':
            state.cancel_waiting(key)
            cancelled += 1
        else:
            raise ValueError('unknown event')
        if event['queued'] != len(state.queue) or event['active'] != len(state.active) or event['limit'] != limit:
            raise ValueError('event state mismatch')
        peak = max(peak, len(state.active))
    return dict(admissions=admissions, releases=releases, cancelled_waits=cancelled,
                peak_active=peak, all_released=not state.active and not state.queue)
