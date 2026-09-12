"""Passive complete-iteration incumbent escrow for a bounded search worker.

No ranking, grading, extra execution, or API calls. Optional only when the
supervisor supplies all three environment fields. These receipts certify a
scientific cutoff, NOT containment of detached processes or exact GPU usage.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import math
import os
from pathlib import Path
import time

FIELDS = ('FORETS_SEARCH_START_NS', 'FORETS_SEARCH_SECONDS', 'FORETS_INCUMBENT_DIR')
_binding = ContextVar('forets_submission_binding', default=None)
_nodes = {}


class SearchBudgetExpired(BaseException):
    """Not a model/candidate failure, and must not be swallowed by retries."""


def admit_request(*, clock_ns=time.monotonic_ns):
    spec = budget()
    if spec is not None and spec[1] - clock_ns() <= 135 * 10**9:
        # Actual transport timeout is 120s. Same 15s reserve for both arms.
        raise SearchBudgetExpired('insufficient search time for a bounded API request')


def encode(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def budget(environment=None):
    env = os.environ if environment is None else environment
    values = [env.get(key) for key in FIELDS]
    if not any(values):
        return None
    if not all(values):
        raise ValueError('partial search-cutoff configuration')
    start = int(values[0]); seconds = float(values[1]); path = Path(values[2])
    if (start <= 0 or not math.isfinite(seconds) or seconds <= 0 or
            not path.is_absolute() or path.is_symlink()):
        raise ValueError('invalid search-cutoff configuration')
    return start, start + round(seconds * 10**9), path


@contextmanager
def submission_context(code, executed_code):
    """Keep the archive association private; do not add it to agent feedback."""
    if budget() is None:
        yield None
        return
    value = {'code_sha256': sha(code.encode()), 'executed_code_sha256': sha(executed_code.encode()), 'receipt': None}
    token = _binding.set(value)
    try:
        yield value
    finally:
        _binding.reset(token)


def capture_submission(directory, receipt):
    value = _binding.get()
    if value is None:
        return
    if value['receipt'] is not None:
        raise ValueError('multiple archives in one task evaluation')
    directory = Path(directory)
    if not directory.is_absolute() or directory.is_symlink():
        raise ValueError('archive path must be absolute and regular')
    for name, key in [('submission.csv', 'submission_sha256'), ('report.json', 'report_sha256')]:
        path = directory/name
        if path.is_symlink() or sha(path.read_bytes()) != receipt[key]:
            raise ValueError('submission archive changed')
    value['receipt'] = dict(receipt, archive_dir=str(directory), code_sha256=value['code_sha256'],
                            executed_code_sha256=value['executed_code_sha256'])


def remember_submission(node, result):
    if budget() is None:
        return
    receipt = result.get('_forets_submission_archive')
    if receipt is not None:
        if receipt['code_sha256'] != sha(node.code.encode()):
            raise ValueError('node and executed submission code differ')
        # Keyed by object identity, not code: repeated code can have different
        # executions. Hold the object too, preventing id reuse in this worker.
        _nodes[id(node)] = (node, dict(receipt))


def write_private(path, raw):
    with path.open('xb') as stream:
        os.chmod(path, 0o600)
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())


def checkpoint_incumbent(solver, *, clock_ns=time.monotonic_ns):
    spec = budget()
    if spec is None:
        return None
    start, deadline, directory = spec
    now = clock_ns()
    if now < start:
        raise ValueError('monotonic clock origin mismatch')
    if now >= deadline:
        return None
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    node = solver.journal.get_best_node()  # Original selector, not external score.
    receipt = None
    if node is not None:
        stored = _nodes.get(id(node))
        if stored is None or stored[0] is not node:
            raise ValueError('incumbent lacks an exact executed-submission association')
        receipt = dict(stored[1])
        if receipt['code_sha256'] != sha(node.code.encode()):
            raise ValueError('incumbent code changed after execution')
    step = solver.state.current_step
    if type(step) is not int or step < 1:
        raise ValueError('complete positive step required')
    value = dict(schema=1, current_step=step, start_ns=start, deadline_ns=deadline,
                 node_id=None if node is None else str(node.id),
                 code=None if node is None else node.code, submission=receipt,
                 selection='original_journal_get_best_node_after_complete_iteration')
    raw = encode(value)
    data = directory/f'step-{step:06d}.json'
    write_private(data, raw)
    durable_ns = clock_ns()  # AFTER writing and fsync, never a pre-write timestamp.
    if durable_ns < now:
        raise ValueError('monotonic clock moved backwards')
    committed = dict(schema=1, data_file=data.name, data_sha256=sha(raw),
                     durable_ns=durable_ns, deadline_ns=deadline,
                     eligible=durable_ns < deadline)
    write_private(directory/f'step-{step:06d}.commit.json', encode(committed))
    return committed


def read_incumbent(directory, *, expected_start_ns, expected_seconds):
    """Post-closeout reader: all receipts checked, then latest eligible step.

    Never substitute a different archive or choose by external grade. A data
    file with no complete commit (e.g. SIGKILL) is ignored, not repaired.
    """
    directory = Path(directory)
    if directory.is_symlink():
        raise ValueError('incumbent directory is a symlink')
    deadline = expected_start_ns + round(expected_seconds * 10**9)
    rows = []
    for path in sorted(directory.glob('step-*.commit.json')):
        if path.is_symlink():
            raise ValueError('receipt symlink')
        try:
            commit = json.loads(path.read_bytes())
        except json.JSONDecodeError:
            continue  # Interrupted commit cannot authorize the data file.
        data = directory/commit['data_file']
        if (data.parent != directory or data.is_symlink() or
                path.name != data.stem + '.commit.json'):
            raise ValueError('receipt path mismatch')
        raw = data.read_bytes(); value = json.loads(raw)
        if (sha(raw) != commit['data_sha256'] or value['start_ns'] != expected_start_ns or
                value['deadline_ns'] != deadline or commit['deadline_ns'] != deadline or
                type(commit['durable_ns']) is not int or commit['durable_ns'] < expected_start_ns or
                commit['eligible'] is not (commit['durable_ns'] < deadline)):
            raise ValueError('receipt content or clock mismatch')
        if value['submission'] is not None and sha(value['code'].encode()) != value['submission']['code_sha256']:
            raise ValueError('selected code binding changed')
        if commit['eligible']:
            rows.append((value['current_step'], commit['durable_ns'], value))
    if len({r[0] for r in rows}) != len(rows):
        raise ValueError('duplicate incumbent steps')
    rows.sort()
    if any(a[1] > b[1] for a,b in zip(rows, rows[1:])):
        raise ValueError('incumbent receipt chronology changed')
    return rows[-1][2] if rows else None
