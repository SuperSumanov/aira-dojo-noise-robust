"""Small, Linux-specific building blocks for the chroot Python interpreter."""

from __future__ import annotations

import ctypes
import errno
import fcntl
import json
import os
import shutil
import signal
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

CLONE_NEWNS = 0x00020000
CLONE_NEWPID = 0x20000000
MS_RDONLY = 1
MS_NOSUID = 2
MS_NODEV = 4
MS_NOEXEC = 8
MS_REMOUNT = 32
MS_BIND = 4096
MS_REC = 16384
MS_PRIVATE = 1 << 18
MNT_DETACH = 2
PR_SET_PDEATHSIG = 1
PR_CAPBSET_DROP = 24
PR_SET_NO_NEW_PRIVS = 38

_libc = ctypes.CDLL(None, use_errno=True)
_libc.mount.argtypes = [
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_char_p,
    ctypes.c_ulong,
    ctypes.c_char_p,
]
_libc.mount.restype = ctypes.c_int
_libc.umount2.argtypes = [ctypes.c_char_p, ctypes.c_int]
_libc.umount2.restype = ctypes.c_int
_libc.unshare.argtypes = [ctypes.c_int]
_libc.unshare.restype = ctypes.c_int
_libc.prctl.argtypes = [
    ctypes.c_int,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.c_ulong,
    ctypes.c_ulong,
]
_libc.prctl.restype = ctypes.c_int


def _bytes(value: str | os.PathLike[str] | None) -> bytes | None:
    return None if value is None else os.fsencode(value)


def _check_syscall(result: int, operation: str) -> None:
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, f"{operation}: {os.strerror(error)}")


def mount(
    source: str | os.PathLike[str] | None,
    target: str | os.PathLike[str],
    filesystem: str | None = None,
    flags: int = 0,
    data: str | None = None,
) -> None:
    _check_syscall(
        _libc.mount(_bytes(source), _bytes(target), _bytes(filesystem), flags, _bytes(data)),
        f"mount {source!s} on {target!s}",
    )


def umount(target: str | os.PathLike[str]) -> None:
    result = _libc.umount2(_bytes(target), MNT_DETACH)
    if result != 0 and ctypes.get_errno() not in (errno.EINVAL, errno.ENOENT):
        _check_syscall(result, f"unmount {target!s}")


def unshare(flags: int) -> None:
    _check_syscall(_libc.unshare(flags), "unshare namespaces")


def prctl(option: int, argument: int) -> None:
    _check_syscall(_libc.prctl(option, argument, 0, 0, 0), f"prctl({option})")


def _unescape_mountinfo(value: str) -> str:
    for encoded, decoded in (("\\040", " "), ("\\011", "\t"), ("\\012", "\n"), ("\\134", "\\")):
        value = value.replace(encoded, decoded)
    return value


@dataclass(frozen=True)
class MountInfo:
    mount_id: int
    parent_id: int
    mount_point: Path
    mount_options: frozenset[str]
    filesystem: str
    super_options: frozenset[str]

    @property
    def writable(self) -> bool:
        return "rw" in self.mount_options and "ro" not in self.mount_options


def parse_mountinfo(text: str) -> list[MountInfo]:
    """Parse the fields needed from Linux ``/proc/*/mountinfo``."""
    mounts: list[MountInfo] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        left, separator, right = line.partition(" - ")
        if not separator:
            raise ValueError(f"Malformed mountinfo line: {line}")
        fields = left.split()
        trailing = right.split()
        if len(fields) < 6 or len(trailing) < 3:
            raise ValueError(f"Malformed mountinfo line: {line}")
        mounts.append(
            MountInfo(
                mount_id=int(fields[0]),
                parent_id=int(fields[1]),
                mount_point=Path(_unescape_mountinfo(fields[4])),
                mount_options=frozenset(fields[5].split(",")),
                filesystem=trailing[0],
                super_options=frozenset(trailing[2].split(",")),
            )
        )
    return mounts


def read_mountinfo() -> list[MountInfo]:
    return parse_mountinfo(Path("/proc/self/mountinfo").read_text(encoding="utf-8"))


def remount_tree_readonly(root: Path) -> None:
    """Make every mount in a recursive bind clone read-only, deepest first."""
    clone_mounts = [
        mount_info for mount_info in read_mountinfo() if mount_info.mount_point.is_relative_to(root)
    ]
    clone_mounts.sort(key=lambda mount_info: len(mount_info.mount_point.parts), reverse=True)
    for mount_info in clone_mounts:
        mount(None, mount_info.mount_point, flags=MS_BIND | MS_REMOUNT | MS_RDONLY)


def bind_mount(source: Path, target: Path, *, readonly: bool) -> None:
    mount(source, target, flags=MS_BIND | MS_REC)
    flags = MS_BIND | MS_REMOUNT
    if readonly:
        flags |= MS_RDONLY
    mount(None, target, flags=flags)


def verify_writable_mounts(root: Path, allowed_targets: set[Path]) -> None:
    """Reject writable mounts in the clone unless their exact target is allowlisted."""
    unexpected: list[str] = []
    for mount_info in read_mountinfo():
        target = mount_info.mount_point
        if target == root or target.is_relative_to(root):
            if mount_info.writable and target not in allowed_targets:
                unexpected.append(str(target))
    if unexpected:
        raise RuntimeError("Unexpected writable sandbox mounts: " + ", ".join(sorted(unexpected)))


def ensure_runtime_base(runtime_base: Path) -> None:
    """Create or validate the supervisor-private runtime directory."""
    try:
        runtime_base.mkdir(mode=0o700, parents=True, exist_ok=False)
    except FileExistsError:
        status = runtime_base.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(status.st_mode)
            or status.st_uid != os.geteuid()
            or status.st_mode & 0o077
        ):
            raise PermissionError(
                f"Sandbox runtime base must be an owner-only directory: {runtime_base}"
            )


class UidLease:
    """An inter-process flock lease for a numeric sandbox UID/GID."""

    def __init__(self, uid: int, descriptor: int, path: Path) -> None:
        self.uid = uid
        self.gid = uid
        self.descriptor = descriptor
        self.path = path

    @classmethod
    def acquire(cls, runtime_base: Path, uid_min: int, uid_max: int) -> "UidLease":
        ensure_runtime_base(runtime_base)
        lock_dir = runtime_base / "uid-locks"
        lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        for uid in range(uid_min, uid_max + 1):
            path = lock_dir / f"{uid}.lock"
            descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                os.close(descriptor)
                continue
            return cls(uid, descriptor, path)
        raise RuntimeError(f"No free sandbox UID in [{uid_min}, {uid_max}]")

    def close_in_child(self) -> None:
        """Drop the inherited descriptor without releasing the parent's lease."""
        try:
            os.close(self.descriptor)
        except OSError:
            pass

    def release(self) -> None:
        if self.descriptor < 0:
            return
        try:
            fcntl.flock(self.descriptor, fcntl.LOCK_UN)
        finally:
            os.close(self.descriptor)
            self.descriptor = -1


@dataclass
class SandboxRuntime:
    path: Path
    root: Path
    temporary: Path

    @classmethod
    def create(cls, runtime_base: Path, uid: int, gid: int) -> "SandboxRuntime":
        ensure_runtime_base(runtime_base)
        path = Path(tempfile.mkdtemp(prefix="sandbox-", dir=runtime_base))
        root = path / "root"
        temporary = path / "writable"
        root.mkdir(mode=0o700)
        temporary.mkdir(mode=0o700)
        for name in ("tmp", "run"):
            child = temporary / name
            child.mkdir(mode=0o700)
            os.chown(child, uid, gid)
        return cls(path=path, root=root, temporary=temporary)

    def write_state(self, workspace: Path, uid: int, supervisor_pid: int | None = None) -> None:
        state = {"workspace": str(workspace), "uid": uid, "supervisor_pid": supervisor_pid}
        (self.path / "state.json").write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    def cleanup(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def validate_workspace_path(
    configured_path: str | os.PathLike[str],
    allowed_working_root: str | os.PathLike[str] | None,
    runtime_base: Path,
) -> Path:
    """Validate a dedicated, non-symlink workspace before changing ownership."""
    configured = Path(configured_path).absolute()
    if configured.is_symlink():
        raise ValueError(f"Sandbox workspace must not be a symlink: {configured}")
    workspace = configured.resolve()
    runtime = runtime_base.resolve()
    if workspace == Path("/") or runtime == workspace or runtime.is_relative_to(workspace):
        raise ValueError(f"Unsafe sandbox workspace: {workspace}")
    if workspace.name != "workspace_agent":
        raise ValueError(
            "The sandbox workspace must be a dedicated directory named 'workspace_agent'"
        )

    if allowed_working_root is None:
        pass
    else:
        allowed = Path(allowed_working_root).resolve()
        if allowed == Path("/"):
            raise ValueError("allowed_working_root must be narrower than the filesystem root")
        if workspace == allowed or not workspace.is_relative_to(allowed):
            raise ValueError(f"Workspace {workspace} must be a child of {allowed}")
    return workspace


def chown_tree_no_follow(root: Path, uid: int, gid: int) -> None:
    """Recursively change ownership without ever following a symlink."""
    os.chown(root, uid, gid, follow_symlinks=False)
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        for name in names + files:
            os.chown(Path(directory) / name, uid, gid, follow_symlinks=False)


def ensure_uniform_ownership_no_follow(root: Path, uid: int, gid: int) -> None:
    """Refuse to flatten a pre-existing workspace containing mixed ownership."""
    for directory, names, files in os.walk(root, topdown=True, followlinks=False):
        for name in names + files:
            status = (Path(directory) / name).lstat()
            if (status.st_uid, status.st_gid) != (uid, gid):
                raise ValueError(f"Workspace contains mixed ownership at {Path(directory) / name}")
            if not stat.S_ISDIR(status.st_mode) and status.st_nlink > 1:
                raise ValueError(
                    f"Workspace contains a pre-existing hard link at {Path(directory) / name}"
                )


def close_fds_except(allowed: set[int]) -> None:
    """Close inherited descriptors so they cannot bypass the read-only mount view."""
    for entry in Path("/proc/self/fd").iterdir():
        descriptor = int(entry.name)
        if descriptor in allowed:
            continue
        try:
            os.close(descriptor)
        except OSError:
            pass


def drop_privileges(uid: int, gid: int) -> None:
    """Permanently drop groups, capabilities and all root user IDs."""
    os.setgroups([])
    for capability in range(64):
        result = _libc.prctl(PR_CAPBSET_DROP, capability, 0, 0, 0)
        if result != 0 and ctypes.get_errno() not in (errno.EINVAL, errno.EPERM):
            _check_syscall(result, f"drop capability {capability}")
    os.setresgid(gid, gid, gid)
    os.setresuid(uid, uid, uid)
    prctl(PR_SET_NO_NEW_PRIVS, 1)


def set_parent_death_signal(parent_pid: int, death_signal: int = signal.SIGKILL) -> None:
    prctl(PR_SET_PDEATHSIG, death_signal)
    # PID 1 sees a parent outside its PID namespace as PID 0.
    if os.getppid() not in (0, parent_pid):
        raise ChildProcessError("Parent exited before the sandbox parent-death signal was armed")
