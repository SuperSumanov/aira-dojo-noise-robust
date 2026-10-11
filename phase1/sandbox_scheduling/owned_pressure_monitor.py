"""Opt-in, bounded Linux host sampler for a known owned worker PID.

Usage: python -B owned_pressure_monitor.py PID --output /owned/new.jsonl
Start before the workload. No commands, environments, code, labels, signals,
limit changes or candidate retries. Use a host PID, not a guessed container PID.
One-second observations can miss transients and do not prove EAGAIN causality.
This utility is not deployed automatically on anyone's production jobs.
It adds a process and CPU/I/O work; enable it symmetrically in comparisons and
include it in resource accounting. Do not assume zero observation overhead.
"""
import argparse
import json
import os
from pathlib import Path
import time

import owned_process_pressure as pressure
import owned_cgroup_pressure


def observed_snapshot(pid):
    value=pressure.snapshot(pid)
    value['target_cgroups']=owned_cgroup_pressure.collect(value['owned_descendants'])
    value['scope_note']='host_pressure.limits/cgroups describe the observer; per-process limits and target_cgroups describe verified worker descendants. Unreadable values are not zero.'
    return value


def monitor(pid, output, duration=300, interval=1, snapshot=observed_snapshot,
            monotonic=time.monotonic, sleep=time.sleep):
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError('positive known host PID required')
    if not 1 <= duration <= 21600 or not 1 <= interval <= 10:
        raise ValueError('duration1..21600s and interval1..10s required')
    output = Path(output).resolve()
    if output.parent.stat().st_uid != os.getuid():
        raise PermissionError('output parent must be owned by this real UID')
    first = snapshot(pid)  # UID/identity checked before creating any artifact.
    if not first['root_identity_stable']:
        raise ProcessLookupError('unstable initial worker identity')
    identity = (first['root_pid'], first['root_start_ticks'])
    started = monotonic()
    samples = 0
    reason = 'duration_limit'
    capture_seconds = 0.0
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        def emit(value):
            file.write(json.dumps(value, sort_keys=True, allow_nan=False) + '\n')
            file.flush()
        emit(dict(event='started',root_pid=pid,root_start_ticks=identity[1],
                  duration_seconds=duration,interval_seconds=interval,
                  observer_pid=os.getpid(),observer_adds_process_and_io=True,
                  boundary='Sampled lower bounds, not atomic/exhaustive counts or causal proof; no production deployment implied.'))
        current = first
        while True:
            if not current['root_identity_stable'] or (current['root_pid'], current['root_start_ticks']) != identity:
                reason = 'root_identity_changed'
                break
            root = next((p for p in current.get('owned_descendants', []) if p['pid']==pid), None)
            if root is None:
                reason = 'observation_failed_closed'
                break
            if root['state'] in ('Z','X','x'):
                reason = 'root_exited'
                break
            emit(dict(event='sample', value=current))
            samples += 1
            remaining = duration - (monotonic() - started)
            if remaining <= 0:
                break
            sleep(min(interval, remaining))
            if monotonic() - started >= duration:
                break
            before = monotonic()
            try:
                current = snapshot(pid)
            except (FileNotFoundError, ProcessLookupError):
                reason = 'root_exited_or_changed'
                break
            except (OSError, ValueError, KeyError):
                reason = 'observation_failed_closed'
                break
            finally:
                capture_seconds += monotonic() - before
        end = dict(event='closed', reason=reason, samples=samples,
                   elapsed_seconds=monotonic()-started,
                   subsequent_capture_wall_seconds=capture_seconds,
                   initial_capture_not_in_overhead_total=True)
        emit(end)
    return end


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=300)
    parser.add_argument('--interval', type=float, default=1)
    args = parser.parse_args()
    result = monitor(args.pid, args.output, args.duration, args.interval)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(2 if result['reason']=='observation_failed_closed' else 0)
