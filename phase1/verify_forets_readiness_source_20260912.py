"""Actual patched-source exception propagation; synthetic kernel, no ML work."""
import argparse
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile
from types import SimpleNamespace

SECRET = re.compile(rb'sk-[A-Za-z0-9_.-]{20,}|(?:gh[pousr]_|hf_|github_pat_)[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')


def checked_archive(root):
    info = json.loads((root / 'artifact.json').read_text())
    raw = (root / 'source.tar').read_bytes()
    if hashlib.sha256(raw).hexdigest() != info['archive_sha256']:
        raise ValueError('archive hash')
    members = {}
    with tarfile.open(root / 'source.tar') as archive:
        names = set()
        for item in archive.getmembers():
            name = PurePosixPath(item.name)
            if name.is_absolute() or '..' in name.parts or item.name in names:
                raise ValueError('unsafe/duplicate archive member')
            names.add(item.name)
            if item.isdir():
                continue
            if not item.isfile() or item.name not in info['source_files']:
                raise ValueError('unlisted/non-file member')
            data = archive.extractfile(item).read()
            if SECRET.search(data):
                raise ValueError('credential shape detected; no values printed')
            if hashlib.sha256(data).hexdigest() != info['source_files'][item.name]:
                raise ValueError('source member hash')
            members[item.name] = data
    if set(members) != set(info['source_files']):
        raise ValueError('archive source coverage')
    return info, members


def run(root, check_only=False):
    info, members = checked_archive(root)
    if check_only:
        print(json.dumps(dict(archive_checked=True, members=len(members), credential_hits=0)))
        return
    base = Path('/research/d7/spc/yzyang4')
    if root.parent != base or not root.name.startswith('forets-readiness-source-20260912-'):
        raise ValueError('remote isolated root required')
    source = root / 'source'
    source.mkdir()
    for name, data in members.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    logging.disable(logging.CRITICAL)
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
        LOGGING_DIR=str(root), SUPERIMAGE_DIR=str(base / 'aira-dojo/build/superimage'),
        MLE_BENCH_DATA_DIR=str(base / 'mle-bench-data'), DEFAULT_SLURM_PARTITION='gpu_24h',
        DEFAULT_SLURM_ACCOUNT='gpu', DEFAULT_SLURM_QOS='gpu')
    sys.path.insert(0, str(source / 'src'))
    from dojo.core.interpreters.jupyter.jupyter_code_executor import JupyterCodeExecutor
    from dojo.core.interpreters.jupyter.kernel_readiness import KernelReadinessError
    from dojo.solvers.fore_ts.execution_witness import ExecutionWitness

    class NotReady:
        dispatches = 0
        def wait_for_ready(self, timeout_seconds):
            assert timeout_seconds == 120
            return False
        def execute(self, *args, **kwargs):
            self.dispatches += 1
            raise AssertionError('must not dispatch candidate')

    kernel = NotReady()
    executor = JupyterCodeExecutor.__new__(JupyterCodeExecutor)
    executor._jupyter_kernel_client = kernel
    executor._wait_timeout, executor._timeout = 120, 300
    class Ledger:
        completed = []
        def begin_task_call(self, slot, intent, max_calls):
            return 1
        def finish_task_call(self, *args):
            self.completed.append(args)
    class Task:
        def step_task(self, state, action):
            return state, {'output': executor.execute_code(action)}
    ledger = Ledger()
    witness = ExecutionWitness(ledger, Task(), 1, 300, 'output')
    raised = None
    try:
        witness.call(0, 'candidate', {'solver_interpreter': SimpleNamespace(timeout=300)},
                     'not_dispatched_candidate()')
    except KernelReadinessError as exc:
        raised = type(exc).__name__
    assert raised == 'KernelReadinessError' and kernel.dispatches == 0
    assert len(ledger.completed) == 1
    entry = ledger.completed[0]
    assert entry[1] == 'raised' and entry[3] is None and entry[4] == raised
    # Positive control: ordinary candidate failures still return as candidate feedback.
    class CodeErrorKernel:
        dispatches = 0
        def wait_for_ready(self, timeout_seconds):
            return True
        def execute(self, code, timeout_seconds):
            self.dispatches += 1
            return SimpleNamespace(timed_out=False, is_ok=False, output=['synthetic code error'])
    ordinary = CodeErrorKernel()
    executor._jupyter_kernel_client = ordinary
    normal = witness.call(1, 'candidate', {'solver_interpreter': SimpleNamespace(timeout=300)},
                          'synthetic_candidate_error()')
    assert normal[1]['output'].exit_code == 1 and not normal[1]['output'].timed_out
    assert ordinary.dispatches == 1 and ledger.completed[-1][1] == 'returned'
    result = dict(utc=dt.datetime.now(dt.timezone.utc).isoformat(), passed=True,
        source_tree=info['source_tree'], controller_commit=info['controller_commit'],
        archive_sha256=info['archive_sha256'], source_files_checked=len(members),
        failure_case=dict(raised=raised, candidate_dispatches=kernel.dispatches,
                          witness_status=entry[1], quality_metadata=entry[3]),
        code_error_control=dict(dispatches=ordinary.dispatches, exit_code=normal[1]['output'].exit_code,
                                witness_status=ledger.completed[-1][1]),
        gpu_jobs=0, api_calls=0, real_candidate_executions=0,
        activated_paid_release=False,
        limitation='Actual production executor/witness imports with synthetic kernel. Not a live failure-rate or e2e gain test.')
    with (root / 'integration-verification.json').open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    run(args.root.resolve(strict=True), args.check_only)
