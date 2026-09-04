"""Quarantine one exact observed file; never submit a job or change tracked code."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

ROOT = Path('/research/d7/spc/yzyang4/worktrees/critic-g0-final-only-20260903-b')
SOURCE_COMMIT = '5f3bc362db922c8edee2ef134656dfdb9a2b74fb'
LOCK = ROOT / 'uv.lock'
LOCK_SHA = 'e4ce9bf353c905d9c360e9bd3eb869f7db3281f4cb23ef203cd590253feaeb0d'
OUT = Path('/research/d7/spc/yzyang4/critic-component-g0/source-repair-12288-20260904')
EXPECTED_STATUS = b'?? uv.lock\n'


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def write_once(path, value):
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
        f.flush(); os.fsync(f.fileno())


def main():
    if ROOT.is_symlink() or ROOT.resolve(strict=True) != ROOT or OUT.parent.resolve(strict=True) != OUT.parent:
        raise RuntimeError('unexpected_root_resolution')
    if git('rev-parse', 'HEAD').decode().strip() != SOURCE_COMMIT:
        raise RuntimeError('source_commit_changed')
    before_status = git('status', '--porcelain', '--untracked-files=all')
    if before_status != EXPECTED_STATUS or git('diff', '--name-only', 'HEAD').strip():
        raise RuntimeError('not_the_exact_single_untracked_lock')
    queue = subprocess.check_output(['squeue', '-u', 'yzyang4', '-h', '-o', '%i'],
                                   env=dict(os.environ, SLURM_CONF='/opt1/slurm/gpu-slurm.conf'))
    if queue.strip():
        raise RuntimeError('active_or_pending_job_do_not_mutate_source')
    if LOCK.is_symlink() or not LOCK.is_file() or LOCK.resolve(strict=True).parent != ROOT:
        raise RuntimeError('unsafe_lock_path')
    observed = LOCK.stat()
    raw = LOCK.read_bytes()
    if observed.st_size != 1035259 or observed.st_uid != os.getuid() or hashlib.sha256(raw).hexdigest() != LOCK_SHA:
        raise RuntimeError('lock_binding_mismatch')
    shape = re.compile(rb'(?i)(?<![A-Za-z0-9])(?:sk-(?:or-v1-)?[A-Za-z0-9_.-]{12,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{30,}|Bearer[ \t]+[A-Za-z0-9._-]{20,})')
    if shape.search(raw):
        raise RuntimeError('credential_shape_hit_no_content_disclosed')
    root_mode = stat.S_IMODE(ROOT.stat().st_mode)
    OUT.mkdir(mode=0o700, exist_ok=False)
    before = dict(utc=datetime.now(timezone.utc).isoformat(), source_commit=SOURCE_COMMIT,
                  source_root=str(ROOT), exact_status='?? uv.lock', lock_bytes=observed.st_size,
                  lock_sha256=LOCK_SHA, lock_inode=observed.st_ino, lock_device=observed.st_dev,
                  lock_mode=stat.S_IMODE(observed.st_mode), lock_mtime_ns=observed.st_mtime_ns,
                  source_root_mode_before=root_mode, credential_shape_hits=0,
                  git_tracked_diff_paths=0, queue_empty=True)
    write_once(OUT/'before.json', before)
    target = OUT/'quarantined-uv.lock'
    if target.exists() or target.is_symlink():
        raise RuntimeError('quarantine_target_exists')
    # Exact same-filesystem rename, preserving bytes and evidence; never recursive.
    if LOCK.stat().st_ino != observed.st_ino or hashlib.sha256(LOCK.read_bytes()).hexdigest() != LOCK_SHA:
        raise RuntimeError('lock_changed_before_move')
    os.rename(LOCK, target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != LOCK_SHA or target.stat().st_ino != observed.st_ino:
        raise RuntimeError('quarantine_identity_mismatch')
    target.chmod(0o400)
    # Only the dedicated checkout root: stop uv.lock/.venv being created there.
    # This is not a claim that every descendant or same-user process is immutable.
    ROOT.chmod(root_mode & ~0o222)
    after_status = git('status', '--porcelain', '--untracked-files=all')
    if after_status.strip() or git('rev-parse', 'HEAD').decode().strip() != SOURCE_COMMIT:
        raise RuntimeError('source_not_restored')
    after = dict(status='EXACT_LOCK_QUARANTINED_SOURCE_CLEAN_NOT_GPU_VALIDATED',
                 source_commit=SOURCE_COMMIT, source_root=str(ROOT), source_clean=True,
                 quarantine_path=str(target), quarantine_sha256=LOCK_SHA,
                 source_root_mode_after=stat.S_IMODE(ROOT.stat().st_mode),
                 root_writable_by_current_process=os.access(ROOT, os.W_OK),
                 source_root_original_mode=root_mode, tracked_source_files_changed=0,
                 known_failure_gate_disabled=False, training_config_changed=False,
                 frozen_protocols_changed=False, new_gpu_jobs=0, model_fits=0,
                 reversible=True, whole_tree_immutable_claim=False)
    if after['root_writable_by_current_process']:
        raise RuntimeError('root_still_writable')
    write_once(OUT/'repair.json', after)
    print(json.dumps(after, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(status='REPAIR_FAILED_CLOSED', exception_type=type(exc).__name__)))
        raise SystemExit(1)
