"""Real installed MCTS generation permits across eight CPU-only processes.

The old CLOSED root supplies read-only dependencies. Repaired entry is copied
to a fresh fixture; no old experiment or readout is modified. Only the model
body is a blocking stub. This is not live model capacity or search acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

OLD = Path('/research/d7/spc/yzyang4/scheduling-generation-quota-20261017-v1')
PLAN = 'f08b3052fcecf467f500b5b9aa6638087c602321ca3a81bf22ef8b65a55b41f9'
ENTRY = 'generation_quota_trial_20261017.py'
ENTRY_SHA = 'ec1b52590b7bda69cc6d651f53a3d9588e84a14cdae3764d0eb2d34eb31df2b6'
SECRET = re.compile(rb'(?i)(?<![a-z0-9])(?:sk-[a-z0-9_.-]{12,}|hf_[a-z0-9]{20,}|gh[pousr]_[a-z0-9]{20,}|Bearer\s+[a-z0-9_.-]{20,})')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    raw = Path(p).read_bytes()
    if SECRET.search(raw):
        raise ValueError('credential-shaped fixture input refused')
    return json.loads(raw)


def wait_until(predicate, seconds=15):
    end = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= end:
            raise TimeoutError('bounded CPU fixture synchronization timeout')
        time.sleep(.025)


def forbidden(*args, **kwargs):
    raise AssertionError('GPU/kernel/model call forbidden in CPU fixture')


def worker(fixture, index):
    sys.path.insert(0, str(fixture))
    sys.path.insert(1, str(OLD))
    os.environ.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1',
                      SLURM_JOB_ID='111', CUDA_VISIBLE_DEVICES='',
                      PRIMARY_KEY='offline-fixture', PRIMARY_KEY_QWEN3_8_27B='offline-fixture')
    import generation_quota_trial_20261017 as trial
    assert sha(trial.__file__) == ENTRY_SHA
    trial.host().setup()
    from dojo.solvers.mcts.mcts import MCTS
    from dojo.utils.experiment_deadline import ExperimentDeadline
    from dojo.core.interpreters.jupyter.jupyter_client import JupyterKernelClient
    from dojo.core.solvers.llm_helpers.generic_llm import GenericLLM

    row = trial.schedule()[index]
    group = 'a' if index % 2 == 0 else 'b'
    ep = fixture / f'episode-{index}'
    ep.mkdir()

    def model_body(self, *args, **kwargs):
        (fixture / f'entered-{index}').touch(exist_ok=False)
        wait_until(lambda: (fixture / f'release-{group}').exists(), 45)
        return None

    # Replace the pre-install model body, not the installed permit wrapper.
    MCTS._analyze = model_body
    with patch.object(JupyterKernelClient, '__init__', forbidden), patch.object(GenericLLM, '__call__', forbidden):
        actual = trial.runtime_hook_guard()
        actual.install_hooks(row, ep, ExperimentDeadline(90))
        import feedback_parent_policy_20261012 as parent
        assert parent.select_request.quota_mode == row['quota_mode']
        (fixture / f'ready-{index}').touch(exist_ok=False)
        wait_until(lambda: (fixture / f'go-{group}').exists(), 45)
        MCTS._analyze(object())
    print(json.dumps(dict(index=index, mode=row['quota_mode'], passed=True,
                         gpu_calls=0, kernel_calls=0, model_calls=0)))


def run_case(stage, mode):
    fixture = Path(tempfile.mkdtemp(prefix=f'quota-concurrent-{mode}-', dir=stage))
    os.chmod(fixture, 0o700)
    shutil.copyfile(stage / ENTRY, fixture / ENTRY)
    assert sha(fixture / ENTRY) == ENTRY_SHA
    sys.path.insert(0, str(OLD))
    import feedback_parent_policy_20261012 as parent
    block = 0 if mode == 'partitioned' else 1
    indices = list(range(block * 8, block * 8 + 8))
    tasks = ('aerial-cactus-identification', 'denoising-dirty-documents')
    rows = [dict(index=i, task=tasks[i % 2]) for i in indices]
    # No experiment code or label is needed for Analyze-only permit exercise.
    warm = {t: dict(code='fixture-' + t, plan='', analysis='', _term_out='',
                    exec_time=0, metric=0., metric_maximize=True) for t in tasks}
    directory = fixture / f'generation-{block}'
    parent.initialize(directory, rows, warm)
    children = []
    snapshots = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHON_DOTENV_DISABLED='1', CUDA_VISIBLE_DEVICES='',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    try:
        for i in indices:
            log = (fixture / f'worker-{i}.private.log').open('xb')
            p = subprocess.Popen([sys.executable, '-B', __file__, '--fixture', str(fixture), '--index', str(i)],
                                 cwd=fixture, env=env, stdout=log, stderr=subprocess.STDOUT)
            children.append((i, p, log))
        wait_until(lambda: all((fixture / f'ready-{i}').exists() for i in indices), 60)

        def counts():
            state = read(directory / 'state.json')
            return dict(active_a=sum(r['task'] == tasks[0] for r in state['active']),
                        active_b=sum(r['task'] == tasks[1] for r in state['active']),
                        waiting_a=sum(r['task'] == tasks[0] for r in state['waiting']),
                        waiting_b=sum(r['task'] == tasks[1] for r in state['waiting']))

        (fixture / 'go-a').touch()
        expected = dict(active_a=2 if mode == 'partitioned' else 4, active_b=0,
                        waiting_a=2 if mode == 'partitioned' else 0, waiting_b=0)
        wait_until(lambda: counts() == expected)
        snapshots.append(dict(stage='only_task_a_requested', **counts()))
        (fixture / 'go-b').touch()
        expected = dict(active_a=2 if mode == 'partitioned' else 4, active_b=2 if mode == 'partitioned' else 0,
                        waiting_a=2 if mode == 'partitioned' else 0, waiting_b=2 if mode == 'partitioned' else 4)
        wait_until(lambda: counts() == expected)
        snapshots.append(dict(stage='both_tasks_requested', **counts()))
        (fixture / 'release-a').touch()
        expected = dict(active_a=0, active_b=2 if mode == 'partitioned' else 4,
                        waiting_a=0, waiting_b=2 if mode == 'partitioned' else 0)
        wait_until(lambda: counts() == expected)
        snapshots.append(dict(stage='task_a_released', **counts()))
        (fixture / 'release-b').touch()
        for i, p, log in children:
            assert p.wait(timeout=20) == 0, f'CPU worker failed: {i}'
        assert counts() == dict(active_a=0, active_b=0, waiting_a=0, waiting_b=0)
        assert not read(directory / 'state.json')['pending']
        raw = (directory / 'events.jsonl').read_bytes()
        assert not SECRET.search(raw)
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        # Separate event replay: no production selector call.
        from generation_quota_policy_20261017 import metadata_audit
        audit = metadata_audit(events, mode)
        assert audit['requests'] == 8 and audit['peak_active'] == 4
        assert (audit['borrowed_admissions'] > 0) == (mode == 'pooled')
        return dict(mode=mode, fixture=str(fixture), snapshots=snapshots, audit=audit,
                    events=events, events_sha256=sha(directory / 'events.jsonl'),
                    worker_indices=indices, passed=True, gpu_calls=0, kernel_calls=0, model_calls=0)
    finally:
        for i, p, log in children:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill(); p.wait(timeout=5)
            log.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--fixture', type=Path)
    p.add_argument('--index', type=int)
    a = p.parse_args()
    assert sha(OLD / 'plan.json') == PLAN and (OLD / 'closed.json').is_file()
    if a.fixture:
        worker(a.fixture, a.index)
        return
    stage = Path(__file__).parent
    assert sha(stage / ENTRY) == ENTRY_SHA
    result = dict(reader_sha256=sha(__file__), entry_sha256=ENTRY_SHA, old_plan_sha256=PLAN,
                  cases=[run_case(stage, mode) for mode in ('partitioned', 'pooled')],
                  limitations=['CPU-only real installed generation permits; model body is a blocking stub.',
                               'No live vLLM capacity, GPU isolation, search, or final-quality result.',
                               'Closed19004 remains invalid and untouched; no old gate/readout is rerun.'])
    assert sha(OLD / 'plan.json') == PLAN
    dest = stage / 'quota-multiprocess-20261017.safe.json'
    with dest.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
    print(json.dumps(dict(passed=True, sha256=sha(dest), cases=[dict(mode=c['mode'], **c['audit']) for c in result['cases']],
                         gpu_calls=0, kernel_calls=0, model_calls=0)))


if __name__ == '__main__':
    main()
