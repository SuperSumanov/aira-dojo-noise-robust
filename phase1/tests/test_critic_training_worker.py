import os
from pathlib import Path
import subprocess
import sys

import pytest

from phase1.critic_training_worker import duration, accounting, allocation_budget, run_group
from phase1.global_local_execution_plan import PlanError


def fixture():
    job = {'job_id': '99991', 'control_root': '/tmp/qualified-source', 'control_commit': 'a'*40,
        'script': '/tmp/qualified-source/worker.sbatch', 'python': '/tmp/runtime/bin/python',
        'job_root': '/tmp/job-99991', 'prior_jobs': [
            {'job_id': '99990', 'state': 'FAILED', 'elapsed_seconds': 149, 'gpus': 2, 'exit_code': '1:0'}],
        'total_gpu_seconds_cap': 4000, 'walltime_seconds': 1560, 'exit_grace_seconds': 60,
        'scheduler_margin_seconds': 60, 'child_timeout_seconds': 1300}
    fields = {'JobId': '99991', 'JobState': 'RUNNING', 'Requeue': '0', 'Restarts': '0', 'NumCPUs': '12',
        'CPUs/Task': '12', 'Partition': 'gpu_24h', 'QOS': 'gpu', 'NumTasks': '1', 'NumNodes': '1',
        'MinMemoryNode': '0', 'TresPerNode': 'gpu:pro6000:2', 'NodeList': 'projgpu39', 'ReqNodeList': 'projgpu39',
        'WorkDir': job['control_root'], 'Command': job['script'], 'TimeLimit': '00:26:00', 'RunTime': '00:00:05',
        'TRES': 'cpu=12,node=1,billing=12,gres/gpu=2'}
    raw = '99990|FAILED|149|cpu=12,gres/gpu=2,node=1|1:0|\n'
    return fields, job, raw


def test_same_budget_includes_failure_and_exit_allowances():
    fields, job, raw = fixture()
    out = allocation_budget(fields, job, raw)
    assert out['prior_allocated_gpu_seconds'] == 298
    assert out['current_reserved_gpu_seconds'] == 3360
    assert out['cumulative_upper_bound_gpu_seconds'] == 3658
    assert out['cap_gpu_seconds'] == 4000


@pytest.mark.parametrize('change', ['cap', 'grace', 'requeued', 'pending', 'wrong_node', 'too_late', 'wall',
                                    'missing_prior', 'active_prior', 'double_row', 'unknown_job', 'current_in_prior', 'allocated_four'])
def test_invalid_allocations_cannot_start(change):
    fields, job, raw = fixture()
    if change == 'cap': job['total_gpu_seconds_cap'] = 3657
    if change == 'grace': job['exit_grace_seconds'] = 1
    if change == 'requeued': fields['Restarts'] = '1'
    if change == 'pending': fields['JobState'] = 'PENDING'
    if change == 'wrong_node': fields['NodeList'] = 'projgpu7'
    if change == 'allocated_four': fields['TRES'] = fields['TRES'].replace('gres/gpu=2', 'gres/gpu=4')
    if change == 'too_late': fields['RunTime'] = '00:05:00'
    if change == 'wall': fields['TimeLimit'] = '01:00:00'
    if change == 'missing_prior': raw = ''
    if change == 'active_prior': raw = raw.replace('FAILED', 'RUNNING')
    if change == 'double_row': raw += raw
    if change == 'unknown_job': raw = raw.replace('99990', '99989')
    if change == 'current_in_prior':
        job['prior_jobs'][0]['job_id'] = '99991'; raw = raw.replace('99990', '99991')
    with pytest.raises(PlanError): allocation_budget(fields, job, raw)


@pytest.mark.parametrize('value', ['Unknown', 'UNLIMITED', '', '1:60:00', '-1:00:00', '1-25:00:00', '30', None])
def test_unknown_duration_is_not_zero(value):
    with pytest.raises(PlanError): duration(value)


def test_explicit_day_duration():
    assert duration('1-00:00:00') == 86400
    assert duration('24:00:00') == 86400


@pytest.mark.parametrize('raw', ['99990.batch|FAILED|149|gres/gpu=2|1:0',
    '99990|FAILED|149|gres/gpu=2,gres/gpu=2|1:0', '99990|FAILED|149|gres/gpu=4|1:0',
    '99990|FAILED|149|gres/gpu=2|0:0', '99990|FAILED|-1|gres/gpu=2|1:0'])
def test_no_double_or_ambiguous_accounting(raw):
    _, job, _ = fixture()
    with pytest.raises(PlanError): accounting(raw, job['prior_jobs'])


def test_no_release_means_no_job_query_or_torch_import(tmp_path):
    code = """
import sys
from pathlib import Path
from phase1.critic_training_worker import main
from phase1.global_local_execution_plan import PlanError
import subprocess
def forbidden(*a, **k): raise AssertionError('access_before_admission')
subprocess.run=forbidden
Path.open=forbidden
sys.argv=['worker','--release-id','not-admitted','--contract-root','/forbidden','--sequence','1']
try: main()
except PlanError as e: assert str(e)=='no_qualified_production_release_registered'
else: raise AssertionError('unexpected_admission')
assert 'torch' not in sys.modules
print('CLOSED_BEFORE_JOB_AND_DATA_ACCESS')
"""
    r = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == 'CLOSED_BEFORE_JOB_AND_DATA_ACCESS'


@pytest.mark.skipif(os.name != 'posix', reason='Linux process-group behavior requires actual Linux')
def test_real_child_group_timeout(tmp_path):
    import signal
    import time
    # Own synthetic child + grandchild only. No GPU/data/package imports.
    script = """
import subprocess,sys,time,signal,os
signal.signal(signal.SIGTERM,signal.SIG_IGN)
p=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'])
print(str(os.getpid())+','+str(p.pid),flush=True)
time.sleep(60)
"""
    log = tmp_path/'child.log'
    start = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_group([sys.executable, '-c', script], cwd=tmp_path, env=dict(os.environ), log=log,
                  timeout_seconds=2, grace_seconds=1)
    assert time.monotonic()-start < 8
    pids = [int(x) for x in log.read_text().strip().split(',')]
    assert len(pids) == 2
    for pid in pids:
        stat = Path('/proc')/str(pid)/'stat'
        # An init-owned zombie awaiting reaping has no executable workload.
        until = time.monotonic()+1
        while stat.exists() and stat.read_text().split()[2] != 'Z' and time.monotonic() < until:
            time.sleep(.01)
        if stat.exists(): assert stat.read_text().split()[2] == 'Z'


@pytest.mark.skipif(os.name != 'posix', reason='Linux process-group behavior requires actual Linux')
def test_real_child_success_and_no_log_overwrite(tmp_path):
    log = tmp_path/'child.log'
    assert run_group([sys.executable, '-c', 'print("OWN_CHILD_OK")'], cwd=tmp_path, env=dict(os.environ),
        log=log, timeout_seconds=5, grace_seconds=1) == 0
    assert log.read_text().strip() == 'OWN_CHILD_OK'
    with pytest.raises(FileExistsError):
        run_group([sys.executable, '-c', 'raise AssertionError("must-not-start")'], cwd=tmp_path,
                  env=dict(os.environ), log=log, timeout_seconds=5, grace_seconds=1)
