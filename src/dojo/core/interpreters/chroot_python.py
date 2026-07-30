"""Opt-in chroot/mount/PID namespace isolation for the Python interpreter."""

from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import time
import traceback
from pathlib import Path

from dojo.config_dataclasses.interpreter.chroot_python import ChrootPythonInterpreterConfig
from dojo.core.interpreters.linux_sandbox import (
    CLONE_NEWNS,
    CLONE_NEWPID,
    MS_BIND,
    MS_NODEV,
    MS_NOEXEC,
    MS_NOSUID,
    MS_PRIVATE,
    MS_REC,
    SandboxRuntime,
    UidLease,
    bind_mount,
    chown_tree_no_follow,
    close_fds_except,
    drop_privileges,
    ensure_uniform_ownership_no_follow,
    mount,
    remount_tree_readonly,
    set_parent_death_signal,
    umount,
    unshare,
    validate_workspace_path,
    verify_writable_mounts,
)
from dojo.core.interpreters.python import PythonInterpreter


_SANDBOX_HOME_INSTRUCTIONS = """Dojo Python sandbox

The current working directory is the writable agent workspace.
Competition data is available read-only at ./data and /home/data.
Write the final submission to ./submission.csv.
"""


def _kill_namespace_descendants(sig: int) -> None:
    try:
        os.kill(-1, sig)
    except ProcessLookupError:
        pass


def _namespace_init(
    interpreter: "ChrootPythonInterpreter",
    code_inq: multiprocessing.Queue,
    result_outq: multiprocessing.Queue,
    event_outq: multiprocessing.Queue,
    root: Path,
    uid: int,
    gid: int,
    supervisor_pid: int,
    allowed_writable_mounts: set[Path],
) -> None:
    """Run as PID 1 in the new namespace, forwarding signals and reaping children."""
    set_parent_death_signal(supervisor_pid)

    proc_target = root / "proc"
    umount(proc_target)
    # CUDA's NVIDIA driver interface performs procfs operations during device
    # discovery. A read-only proc mount makes cudaGetDeviceCount fail with
    # Error 304 even though /dev/nvidia* is accessible. This is a fresh procfs
    # in the private PID namespace; permit only this exact mount as writable.
    mount("proc", proc_target, "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC)
    allowed_writable_mounts.add(proc_target)
    verify_writable_mounts(root, allowed_writable_mounts)
    os.chroot(root)
    os.chdir("/")

    executor_pid = os.fork()
    if executor_pid == 0:
        # PID 1 installed forwarding handlers above.  The executor must not
        # inherit them: receiving SIGTERM while idle would otherwise invoke a
        # handler that only forwards the signal and keep the session loop alive
        # until PID 1 escalates to SIGKILL.
        for reset_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            signal.signal(reset_signal, signal.SIG_DFL)
        os.chdir(interpreter.working_dir)
        workspace_text = str(interpreter.working_dir)
        temporary = "/tmp" if interpreter.private_tmp else f"{workspace_text}/.tmp"
        cache = f"{workspace_text}/.cache"
        config = f"{workspace_text}/.config"
        local = f"{workspace_text}/.local"
        python_user_site = (
            f"{local}/lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
        )
        inherited_pythonpath = os.environ.get("PYTHONPATH", "")
        os.environ.update(
            {
                "HOME": workspace_text,
                "TMPDIR": temporary,
                "TMP": temporary,
                "TEMP": temporary,
                "XDG_CACHE_HOME": cache,
                "XDG_CONFIG_HOME": config,
                "XDG_DATA_HOME": f"{local}/share",
                "MPLCONFIGDIR": f"{config}/matplotlib",
                "HF_HOME": f"{cache}/huggingface",
                "TORCH_HOME": f"{cache}/torch",
                "NUMBA_CACHE_DIR": f"{cache}/numba",
                "PIP_CACHE_DIR": f"{cache}/pip",
                "PIP_USER": "1",
                "PYTHONUSERBASE": local,
                "PYTHONPATH": (
                    python_user_site
                    if not inherited_pythonpath
                    else f"{python_user_site}{os.pathsep}{inherited_pythonpath}"
                ),
                "CONDA_PKGS_DIRS": f"{workspace_text}/.conda/pkgs",
                "CONDA_ENVS_PATH": f"{workspace_text}/.conda/envs",
            }
        )
        if python_user_site not in sys.path:
            sys.path.insert(0, python_user_site)
        queue_fds = {
            endpoint.fileno()
            for ipc_queue in (code_inq, result_outq, event_outq)
            for endpoint in (ipc_queue._reader, ipc_queue._writer)
        }
        close_fds_except({0, 1, 2, *queue_fds})
        drop_privileges(uid, gid)
        PythonInterpreter._run_session(interpreter, code_inq, result_outq, event_outq)
        os._exit(0)

    terminating = False
    termination_deadline: float | None = None

    def forward_signal(sig: int, _frame: object) -> None:
        nonlocal terminating, termination_deadline
        if sig in (signal.SIGTERM, signal.SIGHUP):
            terminating = True
            termination_deadline = time.monotonic() + 2
        try:
            os.kill(executor_pid, sig)
        except ProcessLookupError:
            pass

    for forwarded in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(forwarded, forward_signal)

    executor_status = 1
    while True:
        try:
            waited_pid, status = os.waitpid(-1, os.WNOHANG if terminating else 0)
        except InterruptedError:
            continue
        except ChildProcessError:
            break
        if waited_pid == executor_pid:
            executor_status = status
            break
        if terminating and termination_deadline is not None:
            if time.monotonic() >= termination_deadline:
                _kill_namespace_descendants(signal.SIGKILL)
            else:
                time.sleep(0.02)

    _kill_namespace_descendants(signal.SIGTERM)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            waited_pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            break
        if waited_pid == 0:
            time.sleep(0.02)
    _kill_namespace_descendants(signal.SIGKILL)
    while True:
        try:
            os.waitpid(-1, 0)
        except (ChildProcessError, InterruptedError):
            break
    os._exit(os.waitstatus_to_exitcode(executor_status) if executor_status else 0)


def _sandbox_supervisor(
    interpreter: "ChrootPythonInterpreter",
    code_inq: multiprocessing.Queue,
    result_outq: multiprocessing.Queue,
    event_outq: multiprocessing.Queue,
    runtime: SandboxRuntime,
    uid: int,
    gid: int,
    creator_pid: int,
    original_owner: tuple[int, int],
) -> None:
    """Construct private mounts, then supervise the PID namespace init process."""
    init_pid: int | None = None
    pending_signal: int | None = None

    def forward(sig: int, _frame: object) -> None:
        nonlocal pending_signal
        pending_signal = sig
        if init_pid is not None and init_pid > 0:
            try:
                os.kill(init_pid, sig)
            except ProcessLookupError:
                pass

    for forwarded in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(forwarded, forward)

    try:
        # SIGTERM gives the supervisor time to stop PID 1 and restore workspace
        # ownership if the trusted creator exits without running its finally block.
        set_parent_death_signal(creator_pid, signal.SIGTERM)
        unshare(CLONE_NEWNS)
        mount(None, "/", flags=MS_REC | MS_PRIVATE)
        mount("/", runtime.root, flags=MS_BIND | MS_REC)

        # MLE-bench prompts and generated solutions commonly use the historical
        # container paths /home/data and /home/instructions.txt.  Build a tiny
        # private /home in this mount namespace so those paths exist without
        # creating anything in the shared host /home directory.
        sandbox_home = runtime.root / "home"
        mount("tmpfs", sandbox_home, "tmpfs", MS_NOSUID | MS_NODEV, "mode=0755,size=1m")
        home_data = sandbox_home / "data"
        home_data.mkdir(mode=0o755)
        bind_mount(interpreter.data_dir, home_data, readonly=True)
        (sandbox_home / "instructions.txt").write_text(
            _SANDBOX_HOME_INSTRUCTIONS,
            encoding="utf-8",
        )
        remount_tree_readonly(runtime.root)

        workspace_target = runtime.root / interpreter.working_dir.relative_to("/")
        bind_mount(interpreter.working_dir, workspace_target, readonly=False)
        allowed_writable = {workspace_target}

        if interpreter.private_tmp:
            for name in ("tmp", "run"):
                target = runtime.root / name
                bind_mount(runtime.temporary / name, target, readonly=False)
                allowed_writable.add(target)

        passwd = runtime.path / "passwd"
        group = runtime.path / "group"
        passwd.write_text(
            f"sandbox:x:{uid}:{gid}:Dojo sandbox:{interpreter.working_dir}:/bin/sh\n",
            encoding="utf-8",
        )
        group.write_text(f"sandbox:x:{gid}:\n", encoding="utf-8")
        bind_mount(passwd, runtime.root / "etc/passwd", readonly=True)
        bind_mount(group, runtime.root / "etc/group", readonly=True)
        verify_writable_mounts(runtime.root, allowed_writable)

        # After CLONE_NEWPID succeeds, this process cannot create queue feeder
        # threads until it forks into the namespace. Keep all fallible mount
        # setup before this point so errors can still use multiprocessing.Queue.
        unshare(CLONE_NEWPID)
        supervisor_pid = os.getpid()
        init_pid = os.fork()
        if init_pid == 0:
            _namespace_init(
                interpreter,
                code_inq,
                result_outq,
                event_outq,
                runtime.root,
                uid,
                gid,
                supervisor_pid,
                allowed_writable,
            )

        if pending_signal is not None:
            forward(pending_signal, None)

        while True:
            try:
                _, status = os.waitpid(init_pid, 0)
                chown_tree_no_follow(interpreter.working_dir, *original_owner)
                os._exit(os.waitstatus_to_exitcode(status))
            except InterruptedError:
                continue
    except BaseException as error:
        try:
            chown_tree_no_follow(interpreter.working_dir, *original_owner)
        except (OSError, ValueError):
            pass
        result_outq.put("Sandbox setup failed:\n" + "".join(traceback.format_exception(error)))
        event_outq.put(("state:ready",))
        event_outq.put(("state:finished", "SandboxSetupError", {"args": [str(error)]}, [], None))
        result_outq.put("<|EOF|>")


class ChrootPythonInterpreter(PythonInterpreter):
    """Python interpreter with a read-only host view and writable workspace."""

    # PID 1 forwards termination and reaps descendants before the supervisor
    # restores workspace ownership, which needs a little longer than a plain
    # Python child process.
    cleanup_grace_seconds = 5.0

    def __init__(self, cfg: ChrootPythonInterpreterConfig, data_dir: Path | None = None) -> None:
        if os.name != "posix" or not Path("/proc/self/mountinfo").exists():
            raise RuntimeError("ChrootPythonInterpreter requires Linux")
        if os.geteuid() != 0:
            raise PermissionError(
                "ChrootPythonInterpreter requires root/CAP_SYS_ADMIN during setup"
            )

        self.runtime_base = Path(cfg.runtime_base_dir).resolve()
        workspace = validate_workspace_path(
            cfg.working_dir, cfg.allowed_working_root, self.runtime_base
        )
        if cfg.private_tmp and any(
            workspace == private or workspace.is_relative_to(private)
            for private in (Path("/tmp"), Path("/run"))
        ):
            raise ValueError("A workspace under /tmp or /run is hidden when private_tmp is enabled")
        repository_root = Path(__file__).resolve().parents[4]
        if workspace == repository_root or repository_root.is_relative_to(workspace):
            raise ValueError(
                "The sandbox workspace must not be the repository or one of its ancestors"
            )
        if data_dir is not None:
            resolved_data = Path(data_dir).resolve()
            data_overlaps_workspace = (
                workspace == resolved_data
                or workspace.is_relative_to(resolved_data)
                or resolved_data.is_relative_to(workspace)
            )
            if data_overlaps_workspace:
                raise ValueError(
                    "The sandbox workspace and read-only data directory must not overlap"
                )
        cfg.working_dir = str(workspace)
        self.private_tmp = cfg.private_tmp
        self.uid_min = cfg.uid_min
        self.uid_max = cfg.uid_max
        self._runtime: SandboxRuntime | None = None
        self._uid_lease: UidLease | None = None
        self._original_owner: tuple[int, int] | None = None
        super().__init__(cfg, data_dir=data_dir)

        if self.working_dir.is_symlink() or not self.working_dir.is_dir():
            raise ValueError(f"Sandbox workspace must be a real directory: {self.working_dir}")
        workspace_status = self.working_dir.stat(follow_symlinks=False)
        self._workspace_identity = (workspace_status.st_dev, workspace_status.st_ino)

    def create_process(self) -> None:
        self._close_queues()
        owner = self.working_dir.stat(follow_symlinks=False)
        if (
            self.working_dir.is_symlink()
            or (owner.st_dev, owner.st_ino) != self._workspace_identity
        ):
            raise RuntimeError("Sandbox workspace was replaced after validation")
        self._original_owner = (owner.st_uid, owner.st_gid)
        try:
            self._uid_lease = UidLease.acquire(self.runtime_base, self.uid_min, self.uid_max)
            self._runtime = SandboxRuntime.create(
                self.runtime_base,
                self._uid_lease.uid,
                self._uid_lease.gid,
            )
            self._runtime.write_state(self.working_dir, self._uid_lease.uid)
            ensure_uniform_ownership_no_follow(self.working_dir, owner.st_uid, owner.st_gid)
            if not self.private_tmp:
                (self.working_dir / ".tmp").mkdir(mode=0o700, exist_ok=True)
            for relative in (
                ".cache",
                ".config/matplotlib",
                ".local/share",
                ".conda/pkgs",
                ".conda/envs",
            ):
                (self.working_dir / relative).mkdir(mode=0o700, parents=True, exist_ok=True)
            chown_tree_no_follow(self.working_dir, self._uid_lease.uid, self._uid_lease.gid)

            # Start from a fresh interpreter process. This avoids forking the
            # logger's threads; all later forks happen in the single-threaded
            # supervisor or namespace init process.
            context = multiprocessing.get_context("spawn")
            self.code_inq = context.Queue()
            self.result_outq = context.Queue()
            self.event_outq = context.Queue()
            assert self._original_owner is not None
            self.process = context.Process(
                target=_sandbox_supervisor,
                args=(
                    self,
                    self.code_inq,
                    self.result_outq,
                    self.event_outq,
                    self._runtime,
                    self._uid_lease.uid,
                    self._uid_lease.gid,
                    os.getpid(),
                    self._original_owner,
                ),
            )
            self.process.start()
            self._runtime.write_state(self.working_dir, self._uid_lease.uid, self.process.pid)
        except BaseException:
            self._cleanup_sandbox_resources()
            raise

    def __getstate__(self) -> dict[str, object]:
        """Serialize only executor state when multiprocessing uses ``spawn``."""
        state = self.__dict__.copy()
        state.update(
            {
                "logger": None,
                "process": None,
                "code_inq": None,
                "result_outq": None,
                "event_outq": None,
                "_runtime": None,
                "_uid_lease": None,
                "_original_owner": None,
            }
        )
        return state

    def cleanup_session(self) -> None:
        try:
            super().cleanup_session()
        finally:
            self._cleanup_sandbox_resources()

    def _cleanup_sandbox_resources(self) -> None:
        if self._original_owner is not None and self.working_dir.exists():
            uid, gid = self._original_owner
            chown_tree_no_follow(self.working_dir, uid, gid)
            self._original_owner = None
        if self._runtime is not None:
            self._runtime.cleanup()
            self._runtime = None
        if self._uid_lease is not None:
            self._uid_lease.release()
            self._uid_lease = None
