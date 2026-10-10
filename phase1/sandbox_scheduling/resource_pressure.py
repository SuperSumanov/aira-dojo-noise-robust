"""Linux resource evidence. Never reads cmdlines, environment or task data.

UID totals are visible-process lower bounds, not kernel-enforced ucounts.
Snapshots race with exiting/starting processes; cgroup events are cumulative.
"""
import json
import os
from pathlib import Path
import resource
import socket
import time


def numeric_file(path):
    try:
        raw = path.read_text().strip()
        if raw == 'max':
            return raw
        if raw.isdigit():
            return int(raw)
        rows = [line.split() for line in raw.splitlines()]
        if all(len(r) == 2 and r[1].isdigit() for r in rows):
            return {r[0]: int(r[1]) for r in rows}
        return None
    except (OSError, ValueError):
        return None


def status_fields(raw):
    fields = dict(line.split(':', 1) for line in raw.splitlines() if ':' in line)
    return dict(uid=int(fields['Uid'].split()[0]),
                threads=int(fields['Threads'].strip()),
                ppid=int(fields['PPid'].strip()),
                state=fields['State'].strip().split()[0])


def uid_counts():
    uid = os.getuid()
    rows = []
    denied = 0
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid != uid:
                continue
            row = status_fields((entry / 'status').read_text())
            if row['uid'] == uid:
                rows.append(row)
        except (FileNotFoundError, ProcessLookupError):
            pass
        except (OSError, ValueError, KeyError):
            denied += 1
    return dict(visible_processes=len(rows), visible_threads=sum(r['threads'] for r in rows),
                zombies=sum(r['state'] == 'Z' for r in rows),
                largest_process_thread_counts=sorted((r['threads'] for r in rows), reverse=True)[:12],
                unreadable_or_racing=denied, lower_bound=True)


def cgroups():
    """Read relevant ancestor counters in either cgroup version, no mutations."""
    result = []
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        _, controllers, group = line.split(':', 2)
        if '..' in Path(group).parts:
            continue
        if controllers == '':
            root = Path('/sys/fs/cgroup')
            names = ('pids.current', 'pids.max', 'pids.events', 'memory.current',
                     'memory.max', 'memory.events')
        elif 'pids' in controllers.split(','):
            root = Path('/sys/fs/cgroup/pids')
            names = ('pids.current', 'pids.max', 'pids.events')
        elif 'memory' in controllers.split(','):
            root = Path('/sys/fs/cgroup/memory')
            names = ('memory.usage_in_bytes', 'memory.limit_in_bytes', 'memory.failcnt',
                     'memory.memsw.usage_in_bytes', 'memory.memsw.limit_in_bytes')
        else:
            continue
        target = root / group.lstrip('/')
        for depth in range(16):
            counters = {name: numeric_file(target / name) for name in names}
            result.append(dict(controller=controllers or 'v2', ancestor_depth=depth,
                               counters=counters))
            if target == root:
                break
            target = target.parent
    return result


def snapshot():
    limits = {}
    for name in ('RLIMIT_NPROC', 'RLIMIT_NOFILE', 'RLIMIT_AS', 'RLIMIT_STACK'):
        limits[name] = list(resource.getrlimit(getattr(resource, name)))
    own = status_fields(Path('/proc/self/status').read_text())
    meminfo = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
    return dict(time_utc_seconds=time.time(), host=socket.gethostname(), pid=os.getpid(),
                limits=limits, self_threads=own['threads'],
                affinity_count=len(os.sched_getaffinity(0)),
                uid_counts=uid_counts(), cgroups=cgroups(),
                available_memory_kib=int(meminfo['MemAvailable'].split()[0]),
                self_fd_count=len(list(Path('/proc/self/fd').iterdir())),
                threads_max=numeric_file(Path('/proc/sys/kernel/threads-max')),
                pid_max=numeric_file(Path('/proc/sys/kernel/pid_max')))


if __name__ == '__main__':
    print(json.dumps(snapshot(), sort_keys=True))
