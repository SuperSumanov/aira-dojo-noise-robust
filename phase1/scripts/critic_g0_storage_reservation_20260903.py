"""Reserve checkpoint-sized space in the exact output filesystem; no user files touched."""
import argparse
import datetime as dt
import errno
import json
import os
from pathlib import Path

ROOT = Path('/research/d7/spc/yzyang4/critic-component-g0/recovery-20260903-r2')
FILE = ROOT / 'checkpoint-space.reservation'
SIZE = 4 * 1024**3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['reserve', 'release'])
    args = parser.parse_args()
    assert ROOT.resolve(strict=True) == ROOT
    if args.mode == 'reserve':
        method = 'posix_fallocate'
        fd = os.open(FILE, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            try:
                os.posix_fallocate(fd, 0, SIZE)
            except OSError as exc:
                if exc.errno not in (errno.EOPNOTSUPP, errno.ENOSYS, errno.EINVAL):
                    raise
                method = 'zero_write'
                block = b'\0' * (4 * 1024**2)
                for _ in range(SIZE // len(block)):
                    view = memoryview(block)
                    while view:
                        n = os.write(fd, view)
                        view = view[n:]
            os.fsync(fd)
            stat = os.fstat(fd)
            assert stat.st_size == SIZE and stat.st_blocks * 512 >= SIZE
            receipt = {'status': 'CHECKPOINT_SPACE_RESERVED', 'bytes': SIZE,
                       'allocated_bytes': stat.st_blocks * 512, 'method': method,
                       'device': stat.st_dev, 'inode': stat.st_ino, 'uid': stat.st_uid,
                       'path': str(FILE), 'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                       'not_a_quota_limit_query': True}
            with (ROOT / 'storage_receipt.json').open('x') as f:
                json.dump(receipt, f, sort_keys=True, indent=2)
            print(json.dumps(receipt, sort_keys=True))
        finally:
            os.close(fd)
    else:
        receipt = json.loads((ROOT / 'storage_receipt.json').read_text())
        assert not FILE.is_symlink() and FILE.resolve(strict=True) == FILE
        stat = FILE.stat()
        assert stat.st_size == SIZE and stat.st_uid == os.getuid() == receipt['uid']
        assert stat.st_ino == receipt['inode'] and stat.st_dev == receipt['device']
        FILE.unlink()  # Only this run's explicitly validated, regenerable reservation.
        with (ROOT / 'storage_released.json').open('x') as f:
            json.dump({'status': 'OWN_CHECKPOINT_RESERVATION_RELEASED', 'bytes': SIZE,
                       'utc': dt.datetime.now(dt.timezone.utc).isoformat()}, f)
        print('OWN_CHECKPOINT_RESERVATION_RELEASED bytes=' + str(SIZE))


if __name__ == '__main__':
    main()
