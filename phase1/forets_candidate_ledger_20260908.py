"""Private, single-writer batch ledger; NOT an agent/interpreter checkpoint.

No automatic retry of an ambiguous generation, score request, or execution.
SQLite commits preserve completed records. A stale writer lock requires review.
Hashes detect accidental drift, not tampering by the same OS user.
"""
import hashlib
import json
import math
import os
import sqlite3
from pathlib import Path


class LedgerError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class CandidateLedger:
    """Callers must close normally; never delete a lock to recover automatically."""

    def __init__(self, path, binding, count):
        if type(count) is not int or count <= 0:
            raise LedgerError('invalid candidate count')
        self.path = Path(path)
        self.conn = None
        self.lock = self.path.with_suffix(self.path.suffix + '.lock')
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise LedgerError('symlink storage is not supported')
        # Only a new private leaf directory is created; missing ancestors fail.
        self.path.parent.mkdir(mode=0o700, exist_ok=True)
        if os.name != 'nt' and self.path.parent.stat().st_mode & 0o077:
            raise LedgerError('ledger directory must be private')
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise LedgerError('writer lock present; inspect before recovery') from None
        os.close(fd)
        self.owns_lock = True
        try:
            new = not self.path.exists()
            if new:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            elif os.name != 'nt' and self.path.stat().st_mode & 0o077:
                raise LedgerError('ledger database must be private')
            self.conn = sqlite3.connect(self.path, timeout=0)
            self.conn.execute('PRAGMA synchronous=FULL')
            self.conn.execute('PRAGMA journal_mode=DELETE')
            if new:
                self.conn.execute('CREATE TABLE snapshot (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, sha256 TEXT NOT NULL)')
                self.data = dict(schema=1, binding=binding, phase='collecting', selected=None,
                                 candidates=[dict(state='pending', node=None, score=None) for _ in range(count)])
                self._write()
            else:
                rows = self.conn.execute('SELECT payload,sha256 FROM snapshot WHERE id=1').fetchall()
                if len(rows) != 1:
                    raise LedgerError('missing ledger snapshot')
                payload, sha = rows[0]
                if hashlib.sha256(payload.encode()).hexdigest() != sha:
                    raise LedgerError('ledger hash drift')
                self.data = json.loads(payload)
                if (self.data['schema'] != 1 or self.data['binding'] != binding
                        or len(self.data['candidates']) != count):
                    raise LedgerError('batch binding mismatch')
        except BaseException:
            self.close()
            raise

    def _write(self):
        payload = canonical(self.data)
        with self.conn:
            self.conn.execute('INSERT OR REPLACE INTO snapshot VALUES (1,?,?)',
                              (payload, hashlib.sha256(payload.encode()).hexdigest()))

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        if self.owns_lock:
            self.lock.unlink(missing_ok=True)
            self.owns_lock = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def ensure_preexecution(self):
        """Only a fully known, pre-execution batch may be continued automatically."""
        if self.data['phase'] not in {'collecting', 'selected'}:
            raise LedgerError('execution or completed batch requires checkpoint reconciliation')
        if any(c['state'] not in {'pending', 'generated', 'scored'} for c in self.data['candidates']):
            raise LedgerError('ambiguous in-flight operation; no automatic retry')

    def _transition(self, slot, before, after, **fields):
        if type(slot) is not int or not 0 <= slot < len(self.data['candidates']):
            raise LedgerError('invalid slot')
        c = self.data['candidates'][slot]
        if c['state'] != before:
            raise LedgerError('unexpected candidate state; no retry')
        c.update(state=after, **fields)
        self._write()

    def begin_generation(self, slot):
        if self.data['phase'] != 'collecting':
            raise LedgerError('selection already locked')
        self._transition(slot, 'pending', 'generating')

    def generated(self, slot, node):
        # The only node fields admitted here are PRE-execution data.
        if (set(node) != {'id', 'ctime', 'code', 'plan', 'operators_used', 'operators_metrics'}
                or not isinstance(node['id'], str) or not node['id']
                or not isinstance(node['code'], str)
                or node['plan'] is not None and not isinstance(node['plan'], str)):
            raise LedgerError('invalid pre-execution node schema')
        canonical(node)  # Reject non-JSON / nonfinite operator metadata before mutation.
        if any(c['node'] and c['node']['id'] == node['id'] for c in self.data['candidates']):
            raise LedgerError('duplicate candidate identity')
        self._transition(slot, 'generating', 'generated', node=node)

    def begin_score(self, slot):
        if self.data['phase'] != 'collecting':
            raise LedgerError('selection already locked')
        self._transition(slot, 'generated', 'scoring')

    def scored(self, slot, score):
        if type(score) not in (int, float) or not math.isfinite(score):
            raise LedgerError('nonfinite or nonnumeric critic score')
        self._transition(slot, 'scoring', 'scored', score=score)

    def select(self, slots):
        if (self.data['phase'] != 'collecting' or not slots
                or any(c['state'] != 'scored' for c in self.data['candidates'])
                or any(type(i) is not int or not 0 <= i < len(self.data['candidates']) for i in slots)
                or len(set(slots)) != len(slots)):
            raise LedgerError('invalid or repeated selection')
        self.data.update(phase='selected', selected=list(slots))
        self._write()

    def begin_execution(self, slot):
        if self.data['phase'] not in {'selected', 'executing'} or slot not in self.data['selected']:
            raise LedgerError('execution outside locked selection')
        pending = [i for i in self.data['selected'] if self.data['candidates'][i]['state'] == 'scored']
        if (not pending or pending[0] != slot or
                any(c['state'] == 'executing' for c in self.data['candidates'])):
            raise LedgerError('execution order or in-flight mismatch')
        self.data['phase'] = 'executing'
        self._transition(slot, 'scored', 'executing')

    def execution_completed(self, slot):
        # Means task + parse + journal + debug/backprop returned, not a durable solver checkpoint.
        self._transition(slot, 'executing', 'completed')

    def finish(self):
        if self.data['phase'] not in {'selected', 'executing'}:
            raise LedgerError('batch not selected')
        for i in self.data['selected']:
            c = self.data['candidates'][i]
            if c['state'] not in {'scored', 'completed'}:
                raise LedgerError('unfinished execution')
        for i in self.data['selected']:
            if self.data['candidates'][i]['state'] == 'scored':
                self.data['candidates'][i]['state'] = 'skipped_budget'
        self.data['phase'] = 'complete'
        self._write()
