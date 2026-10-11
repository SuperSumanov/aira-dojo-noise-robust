"""Numerical cgroup counters for verified owned host processes, not the observer.

No process names, commands, environments, cgroup paths or task data exported.
Only conventional host cgroup mounts are supported. Unreadable counters remain
None; namespaces/mount layouts can limit visibility. Samples are non-atomic.
"""
import hashlib
import os
from pathlib import Path

import owned_process_pressure as process
import resource_pressure as host


def counters(text, cgroup_root=Path('/sys/fs/cgroup')):
    result=[];unsupported=0
    for line in text.splitlines():
        fields=line.split(':',2)
        if len(fields)!=3:unsupported+=1;continue
        _,controllers,group=fields
        if not group.startswith('/') or '..' in Path(group).parts:
            unsupported+=1;continue
        if controllers=='':
            root=cgroup_root;names=('pids.current','pids.max','pids.events','memory.current','memory.max','memory.events')
        elif 'pids' in controllers.split(','):
            root=cgroup_root/'pids';names=('pids.current','pids.max','pids.events')
        elif 'memory' in controllers.split(','):
            root=cgroup_root/'memory';names=('memory.usage_in_bytes','memory.limit_in_bytes','memory.failcnt')
        else:continue
        root=root.resolve();target=(root/group.lstrip('/')).resolve()
        if not target.is_relative_to(root):unsupported+=1;continue
        for depth in range(16):
            result.append(dict(controller=controllers or 'v2',ancestor_depth=depth,
                               counters={name:host.numeric_file(target/name) for name in names}))
            if target==root:break
            target=target.parent
        else:unsupported+=1
    return dict(ancestors=result,unsupported_or_truncated=unsupported,
                path_values_exported=False,mount_layout='conventional-host-assumed')


def collect(records, proc=Path('/proc'), cgroup_root=Path('/sys/fs/cgroup')):
    groups={};skipped=[];uid=os.getuid()
    for row in records:
        pid=row['pid'];directory=proc/str(pid)
        try:
            before=process.process_record(directory,uid)
            if before['start_ticks']!=row['start_ticks']:
                raise ProcessLookupError('identity changed')
            text=(directory/'cgroup').read_text()
            after=process.process_record(directory,uid)
            if (before['pid'],before['start_ticks'])!=(after['pid'],after['start_ticks']):
                raise ProcessLookupError('identity changed')
            key=hashlib.sha256(text.encode()).hexdigest()
            if key not in groups:
                groups[key]=dict(group_sha256=key,members=[],**counters(text,cgroup_root))
            groups[key]['members'].append(pid)
        except (OSError,KeyError,ValueError):skipped.append(pid)
    return dict(groups=list(groups.values()),skipped_or_racing_pids=skipped,
                boundary='Verified-owned process cgroup counters, sampled not atomic. Shared ancestors may include other workloads. Missing/unreadable values are unknown, not zero.')
