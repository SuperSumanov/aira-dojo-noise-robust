"""Bound a local POSIX worker process group; not a Slurm/cgroup substitute.

Run the worker INSIDE an approved Slurm step for GPU work. A process can escape
POSIX groups with setsid(), and SIGKILL of this supervisor bypasses its cleanup.
Cluster-side allocation/step time limits remain required. This module submits
no job, authorizes no budget, and makes no claim about provider-side cancellation.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time


class InterruptedRun(Exception):
    pass


def _positive(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('positive finite time limit required')
    return float(value)


def _group_signal(group, sig):
    try:
        os.killpg(group, sig)
        return True
    except ProcessLookupError:
        return False


def _group_exists(group):
    try:
        os.killpg(group, 0)
        return True
    except ProcessLookupError:
        return False


def _private_file(path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb')


def run_bounded(command, *, cwd, output_dir, wall_seconds, grace_seconds=2., environment=None):
    """Run exactly once, store private raw logs and a non-result summary.

    wall_seconds begins immediately before process creation. TERM grace and the
    final leader wait may each consume grace_seconds; count both in the budget.
    Unknown API charge is never zero. OS uninterruptible sleep is not bounded here.
    """
    if os.name != 'posix':
        raise RuntimeError('POSIX worker required; Windows process groups differ')
    wall_seconds, grace_seconds = _positive(wall_seconds), _positive(grace_seconds)
    if not command or not all(isinstance(arg, str) and arg and '\x00' not in arg for arg in command):
        raise ValueError('nonempty argv required; shell commands are not supported')
    cwd, output_dir = Path(cwd).resolve(strict=True), Path(output_dir)
    if not cwd.is_dir():
        raise ValueError('cwd must be a directory')
    # Exclusive run directory prevents accidental replay/overwriting after interruption.
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    identity = json.dumps(dict(argv=command, cwd=str(cwd)), sort_keys=True).encode()
    summary = dict(schema=1, command_sha256=hashlib.sha256(identity).hexdigest(),
                   wall_seconds=wall_seconds, grace_seconds=grace_seconds,
                   api_cost_usd=None, provider_cancellation_verified=False,
                   containment='posix_process_group_only', started=False)
    # Neither environment nor command contents nor child output enter the summary.
    started = time.monotonic()
    process = None
    handlers = {}
    def interrupted(signum, frame):
        raise InterruptedRun('supervisor interrupted')
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            handlers[sig] = signal.signal(sig, interrupted)
        with _private_file(output_dir / 'stdout.private.log') as stdout, _private_file(output_dir / 'stderr.private.log') as stderr:
            process = subprocess.Popen(command, cwd=cwd, env=environment,
                                       stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL,
                                       start_new_session=True, shell=False)
            summary.update(started=True, pid=process.pid)
            try:
                remaining = max(0., wall_seconds - (time.monotonic() - started))
                code = process.wait(timeout=remaining)
                summary['status'] = 'completed' if code == 0 else 'failed'
            except subprocess.TimeoutExpired:
                summary['status'] = 'timed_out'
    except InterruptedRun:
        summary['status'] = 'interrupted'
    except Exception as exc:
        summary.update(status='launch_or_supervisor_failed', error_type=type(exc).__name__)
    finally:
        # Ignore repeated interrupts while reclaiming only the group we created.
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if process is not None:
                summary['term_sent'] = _group_signal(process.pid, signal.SIGTERM)
                if summary['status'] == 'completed' and summary['term_sent']:
                    # Parent exit zero does not establish that its background
                    # work finished. Reclaim it but do not claim a clean success.
                    summary['status'] = 'completed_with_leftovers'
                cleanup_deadline = time.monotonic() + grace_seconds
                while _group_exists(process.pid) and time.monotonic() < cleanup_deadline:
                    process.poll()
                    time.sleep(min(.02, max(0., cleanup_deadline - time.monotonic())))
                summary['kill_sent'] = _group_signal(process.pid, signal.SIGKILL)
                try:
                    summary['returncode'] = process.wait(timeout=grace_seconds)
                except subprocess.TimeoutExpired:
                    summary['status'] = 'cleanup_unconfirmed'
                    summary['returncode'] = None
            summary['elapsed_seconds'] = time.monotonic() - started
            with _private_file(output_dir / 'summary.json') as output:
                output.write((json.dumps(summary, sort_keys=True, indent=2) + '\n').encode())
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--wall-seconds', type=float, required=True)
    parser.add_argument('--grace-seconds', type=float, default=2.)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.command[1:] if args.command[:1] == ['--'] else args.command
    summary = run_bounded(argv, cwd=args.cwd, output_dir=args.output_dir,
                          wall_seconds=args.wall_seconds, grace_seconds=args.grace_seconds)
    print(json.dumps(summary, sort_keys=True))
    raise SystemExit(0 if summary['status'] == 'completed' else 1)


if __name__ == '__main__':
    main()
