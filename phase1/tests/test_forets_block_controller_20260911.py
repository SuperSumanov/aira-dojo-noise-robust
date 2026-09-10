"""Real pinned pool loop/dispatch code, artificial allocation/process boundary.

No real subprocess can launch from the evaluated pool, and no GPU/model/API or
task data is used. Exact new prepared metadata supplies matrix and launcher caps.
"""
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS

import pytest

from phase1 import forets_block_controller_20260911 as ctl

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def prepared():
    raw = (ROOT/'results/forets_next_package_20260911/prepared.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ctl.PREPARED_SHA
    return json.loads(raw)


@pytest.fixture(scope='module')
def pool_module():
    # Rebuild only this file from reachable senior source + committed patch.
    # Fresh clones need not possess the local, unreferenced composed tree object.
    target = 'src/dojo/core/runners/slurm/srun_pool.py'
    with tempfile.TemporaryDirectory(prefix='forets-pool-test-index-') as temporary:
        index_env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary)/'index'))
        def git(*args):
            return subprocess.check_output(['git', '-c', 'core.autocrlf=false', *args],
                                           cwd=ROOT.parent, env=index_env, timeout=30)
        git('read-tree', '065b0fbaa89e0eb663f2834ec768081f5d56394d')
        git('apply', '--cached', '--include='+target, '--whitespace=error',
            str(ROOT/'upstream_patches/0013-ForeTS-bounded-Slurm-worker-entry-20260909.patch'))
        raw = git('show', ':'+target)
    assert hashlib.sha256(raw).hexdigest() == '12fcf5fc727de820a208ca88ee1bd82c58f97842653c3ce463f8b171903d2b79'
    parsed = ast.parse(raw)
    # Replace only optional application type/accounting imports. Every pool
    # function including run, _launch, _complete_local_step remains unchanged.
    parsed.body = [n for n in parsed.body if not (isinstance(n, ast.ImportFrom)
                   and n.module and n.module.startswith('dojo.'))]
    ns = dict(__name__='forets_pool_fixture', SrunPoolConfig=object, RunConfig=object,
              ACTIVE_STATES={'RUNNING'}, TERMINAL_STATES={'COMPLETED','FAILED','CANCELLED'},
              query_sacct=lambda *_: {})
    # dataclasses resolves its defining module even for artificial fixture types.
    import sys
    import types
    module = types.ModuleType(ns['__name__']); module.__dict__.update(ns)
    sys.modules[module.__name__] = module
    exec(compile(parsed, '<exact-pinned-srun-pool>', 'exec'), module.__dict__)
    return module


class Clock:
    def __init__(self, elapsed=900): self.elapsed = elapsed
    def sleep(self, seconds): self.elapsed += seconds
    def monotonic(self): return float(self.elapsed)


def build_pool(tmp_path, prepared, module, monkeypatch, *, block=1, durations=None,
               exit_codes=None, start=900, service=None, path_delay=0):
    clock = Clock(start)
    spec = ctl.block_spec(prepared, block)
    commands, processes = [], []
    durations = durations or [3930]*4
    exit_codes = exit_codes or [0]*4

    class Process:
        def __init__(self, command, **kwargs):
            assert command[0] == 'srun'
            assert '-m' in command and 'dojo.main_bounded_srun_worker' in command
            i = len(commands)
            commands.append(command)
            self.pid = 1000+i; self.finish = clock.elapsed+durations[i]
            self.code = exit_codes[i]; self.terminated = False
            processes.append(self)
        def poll(self): return self.code if clock.elapsed >= self.finish else None
        def terminate(self): self.finish = clock.elapsed; self.code = -15; self.terminated = True
        def kill(self): self.terminate()
        def wait(self, timeout=None):
            if self.poll() is None: self.terminate()
            return self.code

    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected OS or accounting operation in CPU fixture')

    # Patch the evaluated module only, not global subprocess/time used by pytest.
    monkeypatch.setattr(module, 'subprocess', NS(Popen=Process, run=forbidden,
                                               TimeoutExpired=subprocess.TimeoutExpired))
    monkeypatch.setattr(module, 'time', clock)
    monkeypatch.setattr(module, 'query_sacct', forbidden)

    class Pool(ctl.BlockPoolControl, module.SrunPoolLauncher):
        def _discover_allocation(self):
            return NS(job_id='999999', node_list='ARTIFICIAL', num_nodes=1, num_cpus=12,
                      num_gpus=2, end_time=None)
        def _remaining_seconds(self): return ctl.ALLOCATION_SECONDS-clock.elapsed
        def _validate_paths_on_node(self): clock.sleep(path_delay)
        def _accounting_for_task(self, task): return None

    cfg = NS(**spec.launcher)
    cfg.validate = lambda: None
    run_configs = []
    for run_id in spec.run_ids:
        run = NS(id=run_id, logger=NS(output_dir=str(tmp_path/'runs'/run_id)),
                 task=NS(name='artificial'))
        # No actual RunConfig generation/model/data read is claimed here.
        run.to_typed_dict = lambda run_id=run_id: {'id': run_id, 'fixture': True}
        run_configs.append(run)
    pool = Pool(run_configs, cfg, tmp_path, python_executable=Path(__file__))
    pool.configure_block(spec, service or (lambda: True))
    return pool, clock, commands, processes


@pytest.mark.parametrize('block', [1, 2])
def test_complete_fixed_block_at_bounded_duration(tmp_path, prepared, pool_module, monkeypatch, block):
    pool, clock, commands, _ = build_pool(tmp_path, prepared, pool_module, monkeypatch, block=block)
    result = pool.run()
    assert result['successful'] and result['counts'] == {'completed': 4}
    assert [c[c.index('--run-id')+1] for c in commands] == list(pool._block_spec.run_ids)
    assert clock.elapsed <= ctl.ALLOCATION_SECONDS-ctl.CLEANUP_SECONDS
    for command in commands:
        assert '--time=60' in command
        for name, value in [('--wall-seconds','3540'),('--max-api-attempts','100'),('--max-output-tokens','8192')]:
            assert command[command.index(name)+1] == value
    assert all(t['attempt'] == 1 for t in pool.manifest['tasks'].values())


def test_failed_worker_does_not_drop_partner_retry_or_expand(tmp_path, prepared, pool_module, monkeypatch):
    pool, _, commands, _ = build_pool(tmp_path, prepared, pool_module, monkeypatch, exit_codes=[1,0,0,0])
    assert pool.run()['counts'] == {'failed': 1, 'completed': 3}
    assert len(commands) == 4
    assert Counter(t['attempt'] for t in pool.manifest['tasks'].values()) == {1: 4}
    with pytest.raises(RuntimeError, match='do not rerun'): pool.run()


def test_existing_attempt_is_not_automatically_resumed(tmp_path, prepared, pool_module, monkeypatch):
    pool, _, commands, _ = build_pool(tmp_path, prepared, pool_module, monkeypatch)
    next(iter(pool.manifest['tasks'].values()))['attempt'] = 1
    with pytest.raises(RuntimeError, match='prior execution'): pool.run()
    assert not commands


def test_startup_overrun_preserves_all_unstarted_slots(tmp_path, prepared, pool_module, monkeypatch):
    pool, _, commands, _ = build_pool(tmp_path, prepared, pool_module, monkeypatch, start=901)
    assert pool.run()['counts'] == {'pending': 4}
    assert not commands
    assert {t['reason'] for t in pool.manifest['tasks'].values()} == {'startup_allowance_exhausted'}


def test_path_check_consuming_startup_time_cannot_dispatch(tmp_path, prepared, pool_module, monkeypatch):
    pool, _, commands, _ = build_pool(tmp_path, prepared, pool_module, monkeypatch, path_delay=1)
    with pytest.raises(RuntimeError, match='startup_allowance'): pool.run()
    assert not commands


def test_service_loss_during_last_run_is_detected(tmp_path, prepared, pool_module, monkeypatch):
    holder = {}
    pool, clock, commands, processes = build_pool(tmp_path, prepared, pool_module, monkeypatch,
        durations=[10]*4, service=lambda: holder['clock'].elapsed < 950)
    holder['clock'] = clock
    result = pool.run()
    assert len(commands) == 4 and result['counts'] == {'completed': 3, 'cancelled': 1}
    assert processes[-1].terminated and pool._block_stop_reason == 'critic_service_unavailable'


def test_not_enough_time_for_next_step_does_not_cancel_active_one(tmp_path, prepared, pool_module, monkeypatch):
    # Deliberately exceed the assumed time bound in the simulated third step.
    # The last run must remain unstarted; the third is allowed to finish.
    pool, _, commands, processes = build_pool(tmp_path, prepared, pool_module, monkeypatch,
                                            durations=[3930,3930,4200,3930])
    result = pool.run()
    assert len(commands) == 3 and result['counts'] == {'completed': 3, 'pending': 1}
    assert not any(p.terminated for p in processes)


def test_cleanup_reserve_cancels_a_hung_last_run(tmp_path, prepared, pool_module, monkeypatch):
    pool, clock, _, processes = build_pool(tmp_path, prepared, pool_module, monkeypatch,
                                         durations=[3930,3930,3930,10000])
    assert pool.run()['counts'] == {'completed': 3, 'cancelled': 1}
    assert clock.elapsed == ctl.ALLOCATION_SECONDS-ctl.CLEANUP_SECONDS
    assert processes[-1].terminated


def test_refuses_wrong_matrix_or_block(prepared):
    import copy
    bad = copy.deepcopy(prepared); bad['run_configs'][0]['seed'] = 6
    with pytest.raises(ValueError, match='matrix'): ctl.block_spec(bad, 1)
    for block in (True, 0, 3):
        with pytest.raises(ValueError): ctl.block_spec(prepared, block)


def test_missing_service_prevents_any_dispatch(tmp_path, prepared, pool_module, monkeypatch):
    pool, _, commands, _ = build_pool(tmp_path, prepared, pool_module, monkeypatch, service=lambda: False)
    assert pool.run()['counts'] == {'pending': 4}
    assert not commands


def test_reader_checks_hash_and_bounded_size(tmp_path):
    path = tmp_path/'config.json'
    path.write_bytes(b'{}')
    with pytest.raises(ValueError, match='pinned artifact'): ctl._read(path, '0'*64)
    path.write_bytes(b'x'*(2**21+1))
    with pytest.raises(ValueError, match='large configuration'): ctl._read(path)


def test_reader_rejects_outside_path_before_open(tmp_path, monkeypatch):
    def forbidden(*_): raise AssertionError('must not open outside path')
    monkeypatch.setattr(Path, 'open', forbidden)
    with pytest.raises(ValueError, match='escapes'):
        ctl._read(tmp_path.parent/'outside.json', root=tmp_path)
