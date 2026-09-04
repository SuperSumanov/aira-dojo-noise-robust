"""Zero-GPU smoke for redirecting the senior launcher's shared setup off read-only source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

CREDENTIAL = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|Bearer[ \t]+[A-Za-z0-9._-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
ENV_REL = Path('src/mle_critic/scripts/experiment_env_augmented_data.sh')
ENV_SHA = 'f29d22e8bcc5dd65c34d583e362714435347c19f31ba6d8a0b56e76e7e013b40'
EXPECTED_SOURCE_COMMIT = '5f3bc362db922c8edee2ef134656dfdb9a2b74fb'


def digest(path):
    body = path.read_bytes()
    if CREDENTIAL.search(body):
        raise ValueError('credential_shape')
    return hashlib.sha256(body).hexdigest()


def worker_contract(body):
    required = [b'export MLE_CRITIC_OUTPUT_DIR="$shared_env_output"',
                b'export MLE_CRITIC_LOG_DIR="$shared_env_logs"',
                b'/usr/bin/time -v -o "$resource_usage" bash "$launcher"']
    positions = [body.find(item) for item in required]
    if any(position < 0 for position in positions) or not positions[0] < positions[2] or not positions[1] < positions[2]:
        raise ValueError('worker_contract')
    return True


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--scratch-root', type=Path, required=True)
    args = parser.parse_args()
    source, worker, scratch = args.source_root.resolve(strict=True), args.worker.resolve(strict=True), args.scratch_root.absolute()
    if scratch.exists() or worker.is_symlink() or not worker.is_file():
        raise ValueError('unsafe_paths')
    mode = source.stat().st_mode
    if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError('source_root_not_mode_readonly')
    env_script = source/ENV_REL
    if env_script.is_symlink() or not env_script.is_file() or digest(env_script) != ENV_SHA:
        raise ValueError('env_source_drift')
    worker_body = worker.read_bytes()
    if CREDENTIAL.search(worker_body) or not worker_contract(worker_body):
        raise ValueError('worker_source_gate')
    before_commit = git(source, 'rev-parse', 'HEAD')
    before_status = git(source, 'status', '--porcelain', '--untracked-files=all')
    if before_commit != EXPECTED_SOURCE_COMMIT or before_status:
        raise ValueError('source_git_gate')
    if (source/'outputs').exists():
        raise ValueError('source_outputs_preexists')
    scratch.mkdir(parents=True, mode=0o700)
    setup_output, setup_logs, final_output = scratch/'shared-env-output', scratch/'shared-env-logs', scratch/'output'
    environment = {**os.environ, 'MLE_CRITIC_OUTPUT_DIR': str(setup_output),
                   'MLE_CRITIC_LOG_DIR': str(setup_logs), 'PYTHONDONTWRITEBYTECODE': '1'}
    completed = subprocess.run(['bash', '-c', 'source "$1"', 'bash', str(env_script)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
                               timeout=30, check=False)
    if completed.returncode or completed.stdout or completed.stderr:
        raise RuntimeError('shared_env_source_failed')
    after_commit = git(source, 'rev-parse', 'HEAD')
    after_status = git(source, 'status', '--porcelain', '--untracked-files=all')
    if not setup_output.is_dir() or setup_logs.exists() or final_output.exists():
        raise ValueError('write_location_mismatch')
    if (source/'outputs').exists() or after_commit != before_commit or after_status != before_status:
        raise ValueError('source_mutated')
    return {'status': 'G0_SHARED_ENV_OUTPUT_ISOLATION_SMOKE_PASS',
            'source_commit': before_commit, 'source_status_clean': True,
            'env_script_sha256': ENV_SHA, 'worker_sha256': digest(worker),
            'shared_env_output_created_outside_source': True,
            'shared_env_logs_not_created_by_setup': True,
            'final_output_not_created_by_setup': True, 'source_outputs_created': False,
            'gpu_jobs': 0, 'model_fits': 0, 'api_calls': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(main(), sort_keys=True))
    except Exception as exc:
        print(json.dumps({'status': 'FAILED_CLOSED', 'exception_type': type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)
