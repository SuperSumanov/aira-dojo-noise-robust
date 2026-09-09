"""One explicitly approved paired campaign, using the existing bounded srun pool.

No automatic sbatch submission, API preflight, model acceptance, retry, or resume.
Call only after a separate live-route check and approval of the eight-run budget.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from forets_e2e_package import SOURCE, SOURCE_TREE, PYTHON, write_new, common_config
from forets_pilot_plan import run_order

GPU_PYTHON = '/research/d7/spc/yzyang4/venvs/exp/bin/python'


def install_process_credential():
    """Only the known remote variable; never guess a PRIMARY_KEY's provider."""
    if os.environ.get('OPENROUTER_API_KEY'):
        return
    from dotenv import dotenv_values
    values = set()
    for folder in ('aira-dojo', 'aira-dojo-reproduce'):
        path = Path('/research/d7/spc/yzyang4')/folder/'.env'
        if path.is_file():
            value = dotenv_values(path, interpolate=False).get('OPENROUTER_API_KEY')
            if value:
                values.add(value)
    if len(values) > 1:
        raise RuntimeError('remote OpenRouter entries disagree; do not choose silently')
    if values:
        os.environ['OPENROUTER_API_KEY'] = values.pop()


def validate_inputs(root):
    manifest = json.loads((root/'manifest.json').read_text())
    if manifest.get('source_tree') != SOURCE_TREE or manifest.get('role') != 'forets_e2e_development':
        raise ValueError('not the prepared development package')
    rows = manifest['runs']
    if [(r['task'], r['seed'], r['policy']) for r in rows] != list(run_order()):
        raise ValueError('matrix/order changed')
    configs = []
    for index, row in enumerate(rows):
        expected_id = f"{index:02d}-{row['task']}-s{row['seed']}-{row['policy']}"
        if row['run_id'] != expected_id or row['run_dir'] != 'runs/'+expected_id:
            raise ValueError('unexpected run path or identity')
        payload = (root/'configs'/(expected_id+'.json')).read_bytes()
        if hashlib.sha256(payload).hexdigest() != row['config_sha256']:
            raise ValueError('prepared config changed')
        cfg = json.loads(payload)
        if cfg['logger']['output_dir'] != str(root/'runs'/expected_id):
            raise ValueError('package was moved; resolve it again before approval')
        configs.append(cfg)
    normalized = [common_config(c, run_id=r['run_id'], run_dir=root/r['run_dir']) for c,r in zip(configs,rows)]
    if any(normalized[i] != normalized[i+1] for i in range(0,8,2)):
        raise ValueError('unmatched actual configurations')
    return manifest, configs


def require_execution_ready(*, approved, route_checked, environment):
    if not approved or not route_checked:
        raise RuntimeError('exact matrix approval and live route check are required')
    if not re.fullmatch(r'sk-or-v1-[A-Za-z0-9_-]+', environment.get('OPENROUTER_API_KEY', '')):
        raise RuntimeError('remote OpenRouter credential not installed; no GPU/API work started')
    if not environment.get('SLURM_JOB_ID', '').isdigit() or environment.get('SLURM_STEP_ID', '') not in ('', 'batch'):
        raise RuntimeError('controller belongs in the approved sbatch allocation, not a GPU step')


def execute(root, *, approved, route_checked):
    # This only reads the explicitly named remote credential fields, not chat history.
    install_process_credential()
    require_execution_ready(approved=approved, route_checked=route_checked, environment=os.environ)
    manifest, typed = validate_inputs(root)
    runtime = json.loads((root/'runtime.NOT_CREDENTIALS.json').read_text())
    runtime.pop('credential_instruction')
    os.environ.update(runtime, PRIMARY_KEY=os.environ['OPENROUTER_API_KEY'],
                      DEFAULT_SLURM_PARTITION='gpu_24h', DEFAULT_SLURM_ACCOUNT='gpu',
                      DEFAULT_SLURM_QOS='gpu', PYTHONDONTWRITEBYTECODE='1')
    os.chdir(SOURCE)
    sys.path.insert(0, str(SOURCE/'src'))
    from dojo.config_dataclasses.run import RunConfig
    from dojo.config_dataclasses.launcher.srun_pool import SrunPoolConfig
    from dojo.core.runners.slurm.srun_pool import SrunPoolLauncher
    configs = [RunConfig.from_dict(c) for c in typed]
    for c in configs:
        c.validate()
    launcher = SrunPoolConfig(max_parallel=1, gpus_per_step=1, cpus_per_step=6,
        max_retries=0, step_time_limit_minutes=30, worker_wall_seconds=1740,
        forets_max_api_attempts=40, forets_max_output_tokens=8192,
        step_termination_allowance_seconds=330, min_remaining_seconds_to_launch=2130)
    launcher.validate()
    write_new(root/'campaign.started.json', dict(allocation_id=os.environ['SLURM_JOB_ID'],
        source_tree=SOURCE_TREE, planned_runs=8, automatic_resume=False,
        approval_switch=True, route_readiness_declared=True))
    service = None
    pool = None
    status = dict(status='failed', completed=False, service_cleanup_confirmed=False)
    started = time.monotonic()
    def interrupted(signum, frame):
        raise InterruptedError('campaign interrupted')
    original_handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT,signal.SIGTERM)}
    try:
        class WatchedPool(SrunPoolLauncher):
            def _can_launch(self):
                if service is None or service.poll() is not None:
                    raise RuntimeError('critic service stopped; no further runs will launch')
                return super()._can_launch()
        pool = WatchedPool(configs, launcher, SOURCE, python_executable=PYTHON)
        a = pool.allocation
        if a.num_gpus != 2 or a.num_cpus != 12 or a.node_list != 'projgpu39':
            raise RuntimeError('requires the reviewed two-GPU, twelve-CPU allocation on projgpu39')
        remaining = pool._remaining_seconds()
        if remaining is None or remaining > 270*60 or remaining < 2130:
            raise RuntimeError('allocation deadline outside the reviewed budget')
        # Pool owns the actual config bytes/identity paths. Bind the readout to
        # these, not to the preparation-only suggested command paths.
        actual_manifest = dict(schema=1, role='forets_e2e_development', source_tree=SOURCE_TREE, runs=[])
        for row, expected in zip(manifest['runs'], typed):
            actual_path = Path(pool.manifest['tasks'][row['run_id']]['config_path'])
            raw = actual_path.read_bytes()
            if json.loads(raw) != expected:
                raise ValueError('pool altered a prepared config')
            identity = pool._identity_path(row['run_id'], 1)
            actual_manifest['runs'].append(dict(row, config_sha256=hashlib.sha256(raw).hexdigest(),
                process_summary=str((identity.with_suffix('.bounded')/'execution/summary.json').relative_to(root))))
        write_new(root/'runtime-manifest.json', actual_manifest)
        ready = root/'critic.ready.json'
        command = ['srun', '--jobid='+a.job_id, '--exclusive', '--nodes=1', '--ntasks=1',
            '--cpus-per-task=6', '--gres=gpu:1', '--time=265', '--kill-on-bad-exit=1',
            GPU_PYTHON, str(Path(__file__).with_name('forets_e2e_critic_service.py')),
            '--ready', str(ready)]
        service_env = os.environ.copy()
        for name in tuple(service_env):
            if name.startswith('PRIMARY_KEY') or name in ('OPENROUTER_API_KEY','OPENAI_API_KEY'):
                service_env.pop(name)
        with os.fdopen(os.open(root/'critic.private.log', os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as log:
            service = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, env=service_env)
        ready_deadline = time.monotonic()+300
        while not ready.exists():
            if service.poll() is not None or time.monotonic() >= ready_deadline:
                raise RuntimeError('critic service failed to become ready in five minutes')
            time.sleep(1)
        service_identity = json.loads(ready.read_text())
        if service_identity['allocation_id'] != a.job_id or not service_identity['step_id'].isdigit():
            raise RuntimeError('service identity does not belong to this allocation')
        status['service_startup_seconds'] = service_identity['model_load_and_bind_seconds']
        result = pool.run()
        status.update(status='completed' if result['successful'] else 'incomplete',
                      completed=result['successful'], pool=result)
    except Exception as exc:
        status['error_type'] = type(exc).__name__
        # Exception text/command/environment remain private, never credential-bearing summaries.
        raise
    finally:
        for s in original_handlers:
            signal.signal(s, signal.SIG_IGN)
        try:
            if service is not None:
                ready = root/'critic.ready.json'
                if ready.exists():
                    identity = json.loads(ready.read_text())
                    if identity['allocation_id'] == os.environ['SLURM_JOB_ID'] and identity['step_id'].isdigit():
                        subprocess.run(['scancel','--signal=TERM',identity['allocation_id']+'.'+identity['step_id']],
                                       capture_output=True, timeout=15, check=False)
                if service.poll() is None:
                    service.terminate()
                try:
                    service.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    service.kill()
                    service.wait(timeout=5)
                status['service_srun_exited'] = service.poll() is not None
                # srun exit alone does not prove remote step/cgroup cleanup.
            status['controller_elapsed_seconds'] = time.monotonic()-started
            write_new(root/'campaign.finished.json', status)
        finally:
            for s, handler in original_handlers.items():
                signal.signal(s, handler)
    return status


def collect(root):
    """Keep all eight runs, including not-started/failed ones; no winner selection."""
    from forets_e2e_readout import summarize
    manifest = json.loads((root/'runtime-manifest.json').read_text())
    result = summarize(manifest, root)
    output = root/'readout'
    output.mkdir(mode=0o700, exist_ok=False)
    for field in ('runs', 'pairs'):
        rows = result[field]
        with (output/(field+'.csv')).open('x', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    write_new(output/'summary.json', result)
    budget_rows = []
    for row in manifest['runs']:
        claim = (root/row['process_summary']).parent.parent
        finished = claim/'finished.json'
        value = json.loads(finished.read_text()) if finished.exists() else {}
        budget_rows.append(dict(run_id=row['run_id'],
            reserved_adapter_attempts=value.get('reserved_adapter_attempts'),
            budget_archived=value.get('budget_archived'), api_cost_usd=None))
    write_new(output/'costs.partial.json', dict(runs=budget_rows,
        allocation_gpu_hours=None, initialization_gpu_hours=None,
        note='Wait for allocation sacct after job exit. Reservation counts are not successful API calls.'))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package', type=Path, required=True)
    p.add_argument('--execute-approved-matrix', action='store_true')
    p.add_argument('--live-route-checked', action='store_true')
    args = p.parse_args()
    root = args.package.resolve(strict=True)
    if not args.execute_approved_matrix:
        manifest, _ = validate_inputs(root)
        print(json.dumps(dict(status='PACKAGE_VALID_ONLY', planned_runs=len(manifest['runs']),
                              model_loads=0, external_api_calls=0, slurm_dispatches=0)))
        return
    try:
        result = execute(root, approved=args.execute_approved_matrix, route_checked=args.live_route_checked)
    finally:
        if (root/'runtime-manifest.json').is_file() and not (root/'readout').exists():
            collect(root)
    raise SystemExit(0 if result['completed'] else 1)


if __name__ == '__main__':
    main()
