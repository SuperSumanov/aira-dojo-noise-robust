"""Actual allocation probe on the output filesystem; only our own inode removed.

Not a quota query, not persistent capacity reservation or future-space guarantee.
Never falls back to a sparse truncate or clears any other user's/project's files.
"""
import datetime as dt,json,os
from pathlib import Path
SIZE=64*1024**3


def probe(root):
    root=Path(root)
    if not root.is_absolute() or root.resolve(strict=True)!=root or any(x.is_symlink() for x in (root,*root.parents)):
        raise ValueError('space_probe_root')
    path=root/'own-checkpoint-space-probe.bin';receipt=root/'space-probe.json'
    if path.exists() or receipt.exists() or (root/'space-probe-released.json').exists():raise ValueError('space_probe_already_attempted')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_NOFOLLOW,0o600)
    initial=os.fstat(fd);error=None
    try:
        os.posix_fallocate(fd,0,SIZE);os.fsync(fd)
    except OSError as exc:error={'errno':exc.errno,'type':type(exc).__name__}
    finally:
        final=os.fstat(fd);os.close(fd)
    owned=path.lstat()
    if (owned.st_dev,owned.st_ino)!=(initial.st_dev,initial.st_ino) or owned.st_uid!=os.getuid() or owned.st_nlink!=1 or path.is_symlink():
        raise ValueError('space_probe_inode_changed_do_not_remove')
    passed=error is None and final.st_size==SIZE and final.st_blocks*512>=SIZE
    data={'classification':'OWN_FULL_CHECKPOINT_CAPACITY_PROBE_NOT_FUTURE_GUARANTEE',
        'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'requested_bytes':SIZE,'actual_size':final.st_size,
        'allocated_bytes':final.st_blocks*512,'device':final.st_dev,'inode':final.st_ino,'error':error,'passed':passed,
        'other_files_removed':0,'own_inode_to_be_removed':True}
    with receipt.open('x') as f:json.dump(data,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
    path.unlink()
    with (root/'space-probe-released.json').open('x') as f:json.dump({'own_inode_removed':True,'device':final.st_dev,'inode':final.st_ino},f)
    if not passed:raise ValueError('full_checkpoint_capacity_probe_failed')
    return data
