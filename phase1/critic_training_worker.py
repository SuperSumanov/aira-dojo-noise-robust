"""Bounded worker INSIDE an already-admitted Slurm allocation; never submits.

The production registry remains empty until actual source, GPU, storage and
cost qualification. Each attempt has an exact reviewed launch file. Unknown
accounting, requeues, concurrent prior attempts and deadline expiry fail closed.
This module is a worker guard, not a scheduler or an automatic retry policy.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

from phase1.critic_training_entry import registered_contract
from phase1.critic_training_definition import load_definition, launch_attempt
from phase1.global_local_execution_plan import PlanError


TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE'}


def require(ok, reason):
    if not ok:
        raise PlanError(reason)


def duration(value):
    require(type(value) is str, 'worker_duration_type')
    m = re.fullmatch(r'(?:(\d+)-)?(\d+):(\d\d):(\d\d)', value)
    require(m is not None, 'worker_duration_unknown')
    day, hour, minute, second = (int(x or 0) for x in m.groups())
    require(minute < 60 and second < 60 and (not m.group(1) or hour < 24), 'worker_duration_range')
    return ((day*24+hour)*60+minute)*60+second


def accounting(raw, expected):
    """Exact terminal rows from sacct -X; never count .batch/.extern twice."""
    require(type(expected) is list, 'worker_prior_jobs_type')
    seen, used = {}, 0
    allowed = {}
    for item in expected:
        require(type(item) is dict and set(item) == {'job_id', 'state', 'elapsed_seconds', 'gpus', 'exit_code'},
                'worker_prior_job_schema')
        jid = item['job_id']
        require(type(jid) is str and re.fullmatch('[0-9]+', jid) and jid not in allowed,
                'worker_prior_job_identity')
        require(item['state'] in TERMINAL and type(item['elapsed_seconds']) is int and item['elapsed_seconds'] >= 0
                and type(item['gpus']) is int and item['gpus'] == 2
                and type(item['exit_code']) is str and re.fullmatch(r'\d+:\d+', item['exit_code']),
                'worker_prior_job_terminal')
        allowed[jid] = item
    require(type(raw) is str, 'worker_accounting_text')
    for line in raw.splitlines():
        if not line.strip(): continue
        columns = line.split('|')
        if len(columns) == 6 and columns[-1] == '': columns.pop()
        require(len(columns) == 5, 'worker_accounting_columns')
        jid, state, elapsed, tres, exit_code = columns
        require(jid in allowed and jid not in seen and elapsed.isdigit(), 'worker_accounting_identity')
        pairs = [p.split('=', 1) for p in tres.split(',')]
        require(all(len(x) == 2 for x in pairs) and len({x[0] for x in pairs}) == len(pairs), 'worker_accounting_tres')
        fields = dict(pairs)
        row = allowed[jid]
        require(state == row['state'] and int(elapsed) == row['elapsed_seconds']
                and fields.get('gres/gpu') == str(row['gpus']) and exit_code == row['exit_code'],
                'worker_accounting_drift')
        seen[jid] = True
        used += row['gpus']*row['elapsed_seconds']
    require(set(seen) == set(allowed), 'worker_accounting_missing')
    return used


def allocation_budget(fields, job, prior_raw):
    """Pure metadata check; its result is NOT actual hardware qualification."""
    keys = {'job_id', 'control_root', 'control_commit', 'script', 'python', 'job_root', 'prior_jobs',
            'total_gpu_seconds_cap', 'walltime_seconds', 'exit_grace_seconds', 'scheduler_margin_seconds',
            'child_timeout_seconds'}
    require(type(job) is dict and set(job) == keys, 'worker_job_schema')
    require(type(job['job_id']) is str and re.fullmatch('[0-9]+', job['job_id']), 'worker_job_id')
    require(type(job['control_commit']) is str and re.fullmatch('[0-9a-f]{40}', job['control_commit']), 'worker_commit')
    for key in ('total_gpu_seconds_cap', 'walltime_seconds', 'exit_grace_seconds', 'scheduler_margin_seconds', 'child_timeout_seconds'):
        require(type(job[key]) is int and job[key] > 0, 'worker_budget_positive_integer')
    require(job['exit_grace_seconds'] >= 60 and job['scheduler_margin_seconds'] >= 60, 'worker_exit_allowance')
    exact = {'JobId': job['job_id'], 'JobState': 'RUNNING', 'Requeue': '0', 'Restarts': '0',
        'NumCPUs': '12', 'CPUs/Task': '12', 'Partition': 'gpu_24h', 'QOS': 'gpu',
        'NumTasks': '1', 'NumNodes': '1', 'MinMemoryNode': '0', 'TresPerNode': 'gpu:pro6000:2',
        'NodeList': 'projgpu39', 'ReqNodeList': 'projgpu39',
        'WorkDir': job['control_root'], 'Command': job['script']}
    require(type(fields) is dict and all(fields.get(k) == v for k, v in exact.items()), 'worker_allocation_mismatch')
    resources = [x.split('=', 1) for x in fields.get('TRES', '').split(',')]
    require(all(len(x) == 2 for x in resources) and len({x[0] for x in resources}) == len(resources),
            'worker_allocation_tres_schema')
    resources = dict(resources)
    require(all(resources.get(k) == v for k, v in {'cpu': '12', 'node': '1', 'gres/gpu': '2'}.items()),
            'worker_allocated_resource_count')
    require(duration(fields.get('TimeLimit')) == job['walltime_seconds'], 'worker_walltime_mismatch')
    elapsed = duration(fields.get('RunTime'))
    used = accounting(prior_raw, job['prior_jobs'])
    require(job['job_id'] not in {x['job_id'] for x in job['prior_jobs']}, 'worker_current_in_prior_ledger')
    reserve = 2*(job['walltime_seconds']+job['exit_grace_seconds']+job['scheduler_margin_seconds'])
    require(used+reserve <= job['total_gpu_seconds_cap'], 'worker_cumulative_budget_exceeded')
    available = job['walltime_seconds']-elapsed-job['exit_grace_seconds']-job['scheduler_margin_seconds']
    require(job['child_timeout_seconds'] <= available, 'worker_insufficient_remaining_time')
    return {'prior_allocated_gpu_seconds': used, 'current_reserved_gpu_seconds': reserve,
        'cumulative_upper_bound_gpu_seconds': used+reserve, 'cap_gpu_seconds': job['total_gpu_seconds_cap'],
        'runtime_at_check_seconds': elapsed, 'child_timeout_seconds': job['child_timeout_seconds']}


def run_group(argv, *, cwd, env, log, timeout_seconds, grace_seconds):
    """Linux process group: terminate descendants on timeout or interruption."""
    require(os.name == 'posix', 'worker_posix_required')
    with Path(log).open('xb') as stream:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return child.wait(timeout=timeout_seconds)
        except BaseException:
            try: os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: child.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                child.wait(timeout=grace_seconds)
            # The leader may exit while a descendant ignores TERM.
            try: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--release-id', required=True); p.add_argument('--contract-root', type=Path, required=True)
    p.add_argument('--sequence', type=int, choices=(1, 2, 3, 4), required=True)
    args = p.parse_args()
    launch, launch_sha = registered_contract(args.release_id, args.contract_root)
    definition, definition_sha = load_definition(args.contract_root, launch)
    launch_attempt(launch, definition, args.sequence)
    job = launch.get('job')
    require(type(job) is dict and os.environ.get('SLURM_JOB_ID') == job.get('job_id'), 'worker_actual_job_required')
    require(os.environ.get('SLURM_RESTART_COUNT', '0') == '0', 'worker_environment_restart')
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    def read_command(argv):
        r = subprocess.run(argv, env=env, capture_output=True, timeout=30)
        require(r.returncode == 0, 'worker_metadata_command_failed')
        return r.stdout.decode('utf-8')
    control = Path(job['control_root'])
    require(control.is_absolute() and not any(x.is_symlink() for x in (control, *control.parents)), 'worker_control_path')
    require(read_command(['git', '-C', str(control), 'rev-parse', 'HEAD']).strip() == job['control_commit']
            and not read_command(['git', '-C', str(control), 'status', '--porcelain', '--untracked-files=all']).strip(),
            'worker_exact_clean_code')
    require(Path(__file__).resolve() == control/'phase1/critic_training_worker.py', 'worker_imported_source_path')
    prior_ids = [x['job_id'] for x in job['prior_jobs']]
    prior = read_command(['sacct', '-X', '-n', '-P', '-j', ','.join(prior_ids),
        '--format=JobIDRaw,State,ElapsedRaw,AllocTRES,ExitCode']) if prior_ids else ''
    checked_at = time.monotonic()
    raw = read_command(['scontrol', 'show', 'job', '-o', job['job_id']])
    fields = dict(piece.split('=', 1) for piece in raw.split() if '=' in piece)
    budget = allocation_budget(fields, job, prior)
    root = Path(job['job_root'])
    require(root.is_absolute() and root.parent == Path('/research/d7/spc/yzyang4/critic-development-jobs')
            and root.name == 'job-'+job['job_id'] and root.parent.is_dir()
            and not root.exists() and not any(x.is_symlink() for x in (root, *root.parents)), 'worker_new_job_root')
    require(Path(job['python']) == Path('/research/d7/spc/yzyang4/venvs/critic-blackwell-g0-20260905-r5/bin/python'),
            'worker_pinned_python')
    os.umask(0o077); root.mkdir(mode=0o700)
    def record(name, obj):
        with (root/name).open('x') as out: json.dump(obj, out, sort_keys=True, indent=2)
    # Preserve the two contracts separately; a new allocation does not relabel
    # or invalidate a scientifically identical checkpoint.
    record('worker_context.json', {'launch_contract_sha256': launch_sha,
        'training_definition_sha256': definition_sha, 'budget': budget, 'sequence': args.sequence})
    # Inherit scheduler allocation, not arbitrary API keys, proxies or Python paths.
    clean = {k: v for k, v in os.environ.items() if k.startswith('SLURM_')}
    clean.update(CUDA_VISIBLE_DEVICES=os.environ.get('CUDA_VISIBLE_DEVICES', ''),
        PATH=str(Path(job['python']).parent)+':/usr/local/cuda-12.8/bin:/usr/local/bin:/usr/bin:/bin',
        CUDA_HOME='/usr/local/cuda-12.8', PYTHONPATH=str(control), PYTHONDONTWRITEBYTECODE='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
        OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', MAX_JOBS='2',
        PYTHONHASHSEED='6', CUBLAS_WORKSPACE_CONFIG=':4096:8', NCCL_DEBUG='WARN',
        TORCH_EXTENSIONS_DIR=str(root/'extensions'), TRITON_CACHE_DIR=str(root/'triton'),
        SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    for name in ('extensions', 'triton'): (root/name).mkdir(mode=0o700)
    remaining = job['child_timeout_seconds']-(time.monotonic()-checked_at)
    require(remaining > 0, 'worker_setup_exhausted_deadline')
    argv = [job['python'], '-m', 'torch.distributed.run', '--standalone', '--nnodes=1', '--nproc_per_node=2',
        '-m', 'phase1.critic_training_entry', '--release-id', args.release_id, '--contract-root', str(args.contract_root),
        '--sequence', str(args.sequence)]
    record('command.json', argv)
    def interrupted(signum, frame): raise InterruptedError('worker_interrupted')
    for signum in (signal.SIGTERM, signal.SIGINT): signal.signal(signum, interrupted)
    try:
        rc = run_group(argv, cwd=control, env=clean, log=root/'training.private.log',
            timeout_seconds=remaining, grace_seconds=job['exit_grace_seconds']/2)
        record('worker_terminal.json', {'returncode': rc, 'job_id': job['job_id'],
            'process_exit_not_independent_training_acceptance': True})
        require(rc == 0, 'worker_child_failed')
    except BaseException:
        if not (root/'worker_terminal.json').exists():
            record('worker_terminal.json', {'status': 'INTERRUPTED_OR_TIMEOUT', 'job_id': job['job_id'],
                'automatic_retry': False, 'training_completion_claimed': False})
        raise
    print(json.dumps({'status': 'WORKER_EXITED_PENDING_INDEPENDENT_ACCEPTANCE', 'job_id': job['job_id']}))


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        reason = str(exc) if isinstance(exc, PlanError) and re.fullmatch('[a-z_]+', str(exc)) else 'detail_withheld'
        print(json.dumps({'status': 'TRAINING_WORKER_FAILED_CLOSED', 'reason': reason}))
        raise SystemExit(1)
