"""Independent, read-only operational verification. No data or model loading."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

BASE = Path('/research/d7/spc/yzyang4/critic-component-g0')
OUT = BASE / 'source-repair-12288-20260904'
OLD = BASE / 'recovery-preflight-20260903-r3'
SOURCE = Path('/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b')
COMMIT = '5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
SHAPE = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')


def read_safe(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise RuntimeError('unsafe_operational_file')
    raw = path.read_bytes()
    if SHAPE.search(raw):
        raise RuntimeError('credential_shape_hit_no_content_disclosed')
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def verify():
    require(OUT.resolve(strict=True) == OUT and SOURCE.resolve(strict=True) == SOURCE, 'root_resolution')
    names = ('before.json', 'repair.json', 'static_assets_receipt.json', 'recovery_binding.json')
    raw = {name: read_safe(OUT / name) for name in names}
    docs = {name: json.loads(value) for name, value in raw.items()}
    before, repair = docs['before.json'], docs['repair.json']
    require(read_safe(OUT/'COMPLETE') == b'RECHECK_COMPLETE_NO_SUBMISSION\n', 'not_complete')
    require(read_safe(OUT/'recheck_exit.txt') == b'recheck_exit=0\n', 'nonzero_recheck')
    old_assets = json.loads(read_safe(OLD/'static_assets_receipt.json'))
    new_assets = docs['static_assets_receipt.json']
    require(new_assets['status'] == 'G0_STATIC_ASSETS_PASS', 'assets_gate')
    old_core = {k: v for k, v in old_assets.items() if k != 'created_at_utc'}
    new_core = {k: v for k, v in new_assets.items() if k != 'created_at_utc'}
    require(new_core == old_core, 'asset_or_config_drift')
    require(docs['recovery_binding.json'] == json.loads(read_safe(OLD/'recovery_binding.json')), 'runtime_drift')
    require(repair['source_clean'] and repair['source_commit'] == COMMIT, 'repair_source_binding')
    require(not any(repair[k] for k in ('known_failure_gate_disabled', 'training_config_changed',
                'frozen_protocols_changed', 'new_gpu_jobs', 'model_fits', 'whole_tree_immutable_claim')), 'repair_scope')
    require(before['exact_status'] == '?? uv.lock' and before['git_tracked_diff_paths'] == 0, 'before_scope')
    backup = OUT/'quarantined-uv.lock'
    backup_raw = read_safe(backup)
    require(len(backup_raw) == 1035259 and sha(backup_raw) ==
            'e4ce9bf353c905d9c360e9bd3eb869f7db3281f4cb23ef203cd590253feaeb0d', 'backup_bytes')
    require(backup.stat().st_ino == before['lock_inode'] and backup.stat().st_dev == before['lock_device'], 'backup_identity')
    require(stat.S_IMODE(backup.stat().st_mode) == 0o400, 'backup_mode')
    require(not os.path.lexists(SOURCE/'uv.lock') and not os.path.lexists(SOURCE/'.venv'), 'root_artifact_remains')
    git = lambda *args: subprocess.check_output(['git', '-C', str(SOURCE), *args])
    require(git('rev-parse', 'HEAD').decode().strip() == COMMIT, 'source_head_changed')
    require(not git('status', '--porcelain', '--untracked-files=all').strip(), 'source_not_clean')
    require(stat.S_IMODE(SOURCE.stat().st_mode) == before['source_root_mode_before'] & ~0o222, 'root_mode')
    require(not os.access(SOURCE, os.W_OK), 'source_root_writable')
    for rel, binding in new_assets['source']['artifacts'].items():
        path = SOURCE / rel
        require(path.resolve(strict=True).is_relative_to(SOURCE), 'artifact_escape')
        body = read_safe(path)
        require(len(body) == binding['bytes'] and sha(body) == binding['sha256'], 'source_artifact_drift')
    worker = read_safe(BASE/'runs/job-12288/worker.log')
    require(sha(worker) == 'e3d31e64e13a74a38ef31273826fc51f2317c26c9e583eab341bc60cd8a97776', 'failure_log_drift')
    require(worker == ('G0 contract failure: Git worktree is not clean: ' + str(SOURCE) + '\n').encode(), 'failure_not_exact')
    for name in ('preflight.json', 'accelerate.log', 'gpu_telemetry.csv', 'verification.json', 'COMPLETE', 'output'):
        require(not os.path.lexists(BASE/'runs/job-12288'/name), 'unexpected_training_artifact')
    env = dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf')
    require(not subprocess.check_output(['squeue', '-u', 'yzyang4', '-h', '-o', '%i'], env=env).strip(), 'queue_nonempty')
    account = subprocess.check_output(['sacct', '-X', '-n', '-P', '-j', '12181,12288',
        '--format=JobIDRaw,State,ElapsedRaw,Start,End,AllocTRES,ExitCode'], env=env).decode()
    jobs = []
    for line in account.splitlines():
        if not line.strip():
            continue
        jid, state, elapsed, start, end, tres, code = line.split('|')[:7]
        require(jid in ('12181', '12288') and state == 'FAILED' and code == '1:0', 'accounting_status')
        require('gres/gpu=2' in tres.split(','), 'accounting_gpu')
        require(elapsed == {'12181':'156', '12288':'4'}[jid], 'accounting_elapsed')
        require(re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d', start) and
                re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d', end), 'accounting_time')
        jobs.append(dict(job_id=int(jid), state=state, allocated_gpus=2, elapsed_seconds=int(elapsed),
                         start_hong_kong=start, end_hong_kong=end, exit_code=code))
    require(sorted(j['job_id'] for j in jobs) == [12181, 12288], 'accounting_cardinality')
    used = sum(j['allocated_gpus'] * j['elapsed_seconds'] for j in jobs)
    proposal = 2 * 117 * 60
    return dict(status='SOURCE_REPAIR_AND_STATIC_RECHECK_VERIFIED_NOT_GPU_VALIDATED',
                source_commit=COMMIT, source_clean=True, source_root_mode_octal=oct(stat.S_IMODE(SOURCE.stat().st_mode)),
                source_root_nonwritable=True, quarantine_sha256=sha(backup_raw), quarantine_same_inode=True,
                assets_equal_except_timestamp=True, recovery_binding_equal=True,
                static_assets_sha256=sha(raw['static_assets_receipt.json']),
                recovery_binding_sha256=sha(raw['recovery_binding.json']),
                repair_sha256=sha(raw['repair.json']), before_sha256=sha(raw['before.json']),
                worker_log_sha256=sha(worker), source_artifacts_rehashed=len(new_assets['source']['artifacts']),
                runtime_packages_rechecked=docs['recovery_binding.json']['package_versions_rechecked'],
                runtime_critical_hashes_rechecked=docs['recovery_binding.json']['runtime_critical_hashes_rechecked'],
                job_12288_failed_before_training=True, jobs=sorted(jobs, key=lambda j:j['job_id']),
                allocated_gpu_seconds_used=used, proposed_retry_seconds=117*60,
                proposed_cumulative_gpu_seconds=used+proposal, proposed_cumulative_gpu_hours=(used+proposal)/3600,
                proposed_retry_within_original_4_gpu_hours=used+proposal <= 4*3600,
                new_retry_authorized=False, new_job_submitted=False, queue_empty=True,
                verifier_data_or_model_files_opened=0, protected_cohort_values_read=False)


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status':'INDEPENDENT_VERIFICATION_FAILED_CLOSED', 'exception_type':type(exc).__name__}))
        raise SystemExit(1)
