"""Standalone namespace supervisor. Only stdlib and Dojo Linux primitives are loaded."""
import json
import os
import resource
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

from src.dojo.core.interpreters.linux_sandbox import (
    CLONE_NEWNS, CLONE_NEWPID, MS_PRIVATE, MS_REC, MS_RDONLY, MS_REMOUNT,
    MS_NOSUID, MS_NODEV, mount, bind_mount, remount_tree_readonly, unshare,
    verify_writable_mounts, drop_privileges, close_fds_except, set_parent_death_signal,
)


def setup(config):
    root = Path(config["root"])
    mount("tmpfs", root, "tmpfs", MS_NOSUID | MS_NODEV, "size=32m,mode=755")

    def bind(source, dest, readonly=True):
        source = Path(source)
        target = root / dest.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            target.mkdir(exist_ok=True)
        else:
            target.touch()
        bind_mount(source, target, readonly=readonly)
        if readonly:
            remount_tree_readonly(target)

    for name in ("usr", "bin", "sbin", "lib", "lib64"):
        source = Path("/") / name
        if source.is_symlink():
            (root / name).symlink_to(os.readlink(source))
        elif source.exists():
            bind(source, "/" + name)
    for name in ("ld.so.cache", "nsswitch.conf", "ssl/certs", "localtime"):
        source = Path("/etc") / name
        if source.exists():
            bind(source, "/etc/" + name)
    (root / "etc/passwd").write_text(f"agent:x:{config['uid']}:{config['uid']}:agent:/workspace:/bin/bash\n")
    (root / "etc/group").write_text(f"agent:x:{config['uid']}:\n")
    for source in config["conda_roots"]:
        bind(source, source)
    bind(config["workspace"], "/workspace", False)
    bind(config["public"], "/mnt/data")
    bind(Path(__file__).with_name("editor.py"), "/opt/mle-editor.py")
    for name in ("null", "zero", "random", "urandom"):
        bind("/dev/" + name, "/dev/" + name)


def make_root(config):
    # Kept separate from setup to mount proc only after entering the PID namespace.
    root = Path(config["root"])
    setup(config)
    allowed = {root / "workspace"}
    for name, size in (("tmp", "256m"), ("run", "16m"), ("dev/shm", "256m")):
        target = root / name
        target.mkdir(parents=True, exist_ok=True)
        mount("tmpfs", target, "tmpfs", MS_NOSUID | MS_NODEV, f"size={size},mode=1777")
        allowed.add(target)
    (root / "proc").mkdir()
    mount("proc", root / "proc", "proc", MS_NOSUID | MS_NODEV)
    mount(None, root / "proc", flags=MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV)
    mount(None, root, flags=MS_REMOUNT | MS_RDONLY | MS_NOSUID | MS_NODEV)
    verify_writable_mounts(root, allowed)
    os.chroot(root)
    os.chdir("/workspace")
    os.sched_setaffinity(0, config["cpus"])
    os.nice(10)
    for kind, value in ((resource.RLIMIT_NPROC, 128), (resource.RLIMIT_NOFILE, 1024),
                        (resource.RLIMIT_FSIZE, 1024**3), (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(kind, (value, value))
    drop_privileges(config["uid"], config["uid"])
    # setresuid clears PDEATHSIG. Rearm it after dropping privileges so a lost
    # Ray worker/supervisor also tears down the entire PID namespace.
    set_parent_death_signal(os.getppid())
    close_fds_except({0, 1, 2})
    os.environ.clear()
    os.environ.update({
        "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/workspace", "LANG": "C.UTF-8",
        "TMPDIR": "/tmp", "PYTHONUSERBASE": "/workspace/.local",
        "XDG_CACHE_HOME": "/workspace/.cache", "HF_HOME": "/workspace/.cache/huggingface",
        "TORCH_HOME": "/workspace/.cache/torch", "MPLCONFIGDIR": "/workspace/.cache/matplotlib",
        "CUDA_VISIBLE_DEVICES": "", "NVIDIA_VISIBLE_DEVICES": "void", "ROCR_VISIBLE_DEVICES": "",
        **{key: str(len(config["cpus"])) for key in
           ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
    })


def execute(request, config):
    args = request["arguments"]
    if request["operation"] == "bash":
        command = ["/bin/bash", "--noprofile", "--norc", "-c", args["command"]]
    elif request["operation"] == "text_editor":
        command = ["/usr/bin/python3", "-I", "/opt/mle-editor.py", json.dumps(args)]
    else:
        raise ValueError("Unknown operation")
    start = time.monotonic()
    proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True, close_fds=True)
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    discarded = 0
    timed_out = False
    with selectors.DefaultSelector() as selector:
        for name in buffers:
            pipe = getattr(proc, name)
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map():
            elapsed = time.monotonic() - start
            if elapsed >= request["timeout_s"]:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                # Escaped descendants can retain a pipe; never wait forever on EOF.
                if elapsed > request["timeout_s"] + 1:
                    break
            for key, _ in selector.select(0.05):
                data = os.read(key.fd, 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                room = max(0, config["max_output_bytes"] - len(buffers[key.data]))
                buffers[key.data].extend(data[:room])
                discarded += max(0, len(data) - room)
    if proc.poll() is None:
        try:
            proc.wait(timeout=max(0.01, request["timeout_s"] - (time.monotonic() - start)))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()
    proc.stdout.close()
    proc.stderr.close()
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if not pid:
                break
        except ChildProcessError:
            break
    return {"id": request["id"], "exit_code": proc.returncode, "timed_out": timed_out,
            "duration_s": time.monotonic() - start, "truncated_bytes": discarded,
            **{name: bytes(value).decode("utf-8", errors="replace") for name, value in buffers.items()}}


def serve(config):
    make_root(config)
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        try:
            result = execute(request, config)
        except Exception as error:
            result = {"id": request["id"], "error": f"{type(error).__name__}: {error}"}
        print(json.dumps(result), flush=True)


def main():
    config = json.loads(sys.stdin.readline())
    set_parent_death_signal(os.getppid())
    unshare(CLONE_NEWNS | CLONE_NEWPID | 0x40000000)  # CLONE_NEWNET
    mount(None, "/", flags=MS_REC | MS_PRIVATE)
    pid = os.fork()
    if pid == 0:
        set_parent_death_signal(os.getppid())
        try:
            serve(config)
        except BaseException:
            import traceback
            traceback.print_exc()
            os._exit(1)
        finally:
            os._exit(0)
    else:
        def terminate(signum, frame):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        signal.signal(signal.SIGTERM, terminate)
        _, status = os.waitpid(pid, 0)
        sys.exit(os.waitstatus_to_exitcode(status))


if __name__ == "__main__":
    main()
