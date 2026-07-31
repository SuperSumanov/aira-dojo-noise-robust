from __future__ import annotations

import fcntl
import os
import signal
import shutil
import tempfile
import time
from pathlib import Path

import pytest
import torch

from dojo.config_dataclasses.interpreter.chroot_python import ChrootPythonInterpreterConfig
from dojo.core.interpreters.chroot_python import ChrootPythonInterpreter


def _has_capability(number: int) -> bool:
    status = Path("/proc/self/status").read_text(encoding="utf-8")
    value = status.split("CapEff:\t", 1)[1].splitlines()[0]
    return bool(int(value, 16) & (1 << number))


requires_sandbox_capabilities = pytest.mark.skipif(
    os.geteuid() != 0 or not _has_capability(21) or not _has_capability(18),
    reason="requires root with CAP_SYS_ADMIN and CAP_SYS_CHROOT",
)


@requires_sandbox_capabilities
def test_chroot_interpreter_allows_workspace_and_blocks_host_writes() -> None:
    test_root = Path(tempfile.mkdtemp(prefix="dojo-chroot-integration-", dir=Path.cwd().parent))
    test_root.chmod(0o755)
    workspace = test_root / "workspace_agent"
    workspace.mkdir()
    data = test_root / "data"
    data.mkdir()
    data_file = data / "input.txt"
    data_file.write_text("readable", encoding="utf-8")
    data_file.chmod(0o666)
    sentinel = test_root / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    sentinel.chmod(0o666)
    (workspace / "outside-link").symlink_to(sentinel)
    runtime = test_root / "runtime"
    shm_marker = f"dojo-shm-{test_root.name}"
    host_shm_marker = Path("/dev/shm") / shm_marker
    assert not host_shm_marker.exists()

    interpreter = ChrootPythonInterpreter(
        ChrootPythonInterpreterConfig(
            working_dir=str(workspace),
            allowed_working_root=str(test_root),
            runtime_base_dir=str(runtime),
            uid_min=240000,
            uid_max=240010,
            timeout=30,
        ),
        data_dir=data,
    )
    host_mounts_before = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    original_host_fd = os.open(sentinel, os.O_WRONLY)
    inherited_host_fd = fcntl.fcntl(original_host_fd, fcntl.F_DUPFD, 1000)
    os.close(original_host_fd)
    try:
        multiprocessing_result = interpreter.run(
            f"""
import multiprocessing
import multiprocessing.util
from pathlib import Path

import torch

class SandboxDataset(torch.utils.data.Dataset):
    def __len__(self):
        return 16

    def __getitem__(self, index):
        return torch.tensor(index)

if __name__ == "__main__":
    ipc_queue = multiprocessing.Queue()
    ipc_queue.put("semlock-ok")
    print("multiprocessing", ipc_queue.get(timeout=5))
    ipc_queue.close()
    ipc_queue.join_thread()
    print("multiprocessing-tempdir", multiprocessing.util.get_temp_dir())
    Path("/dev/shm/{shm_marker}").write_text("private-shm")
    loader = torch.utils.data.DataLoader(
        SandboxDataset(),
        batch_size=4,
        num_workers=2,
    )
    print("dataloader-workers", sum(batch.sum().item() for batch in loader))
            """,
            file_name="multiprocessing_isolation.py",
        )
        assert multiprocessing_result.exit_code == 0, "".join(
            multiprocessing_result.term_out
        )
        result = interpreter.run(
            f"""
import os
import signal
import subprocess
import time
import importlib
from pathlib import Path

import numpy
import pandas
import sklearn
import torch

print("uid", os.geteuid(), "groups", os.getgroups())
print("research-imports", numpy.__name__, pandas.__name__, sklearn.__name__, torch.__name__)
print("torch-cuda-available", torch.cuda.is_available())
print("data", Path("data/input.txt").read_text())
print("home-data", Path("/home/data/input.txt").read_text())
print("home-instructions", Path("/home/instructions.txt").is_file())
print("xdg-config", os.environ["XDG_CONFIG_HOME"])
user_site = next(Path(path) for path in __import__("sys").path if "site-packages" in path and str(Path.home()) in path)
user_site.mkdir(parents=True, exist_ok=True)
(user_site / "sandbox_user_package.py").write_text("VALUE = 'user-site-ok'\\n")
importlib.invalidate_caches()
import sandbox_user_package
print("user-site", sandbox_user_package.VALUE)
for variable in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "MPLCONFIGDIR", "HF_HOME", "TORCH_HOME", "NUMBA_CACHE_DIR", "PIP_CACHE_DIR", "CONDA_PKGS_DIRS", "CONDA_ENVS_PATH"):
    target = Path(os.environ[variable])
    target.mkdir(parents=True, exist_ok=True)
    (target / "write-test").write_text(variable)
Path("output.txt").write_text("workspace-write")
for label, path in [("data-relative", Path("data/input.txt")), ("data-home", Path("/home/data/input.txt")), ("home-root", Path("/home/write-test"))]:
    try:
        path.write_text("modified")
    except OSError as error:
        print(label, "blocked", error.errno)
    else:
        print(label, "WRITE_SUCCEEDED")
for label, path in [("outside", Path({str(sentinel)!r})), ("symlink", Path("outside-link"))]:
    try:
        path.write_text("modified")
    except OSError as error:
        print(label, "blocked", error.errno)
    else:
        print(label, "WRITE_SUCCEEDED")
print("subprocess", subprocess.check_output(["/bin/sh", "-c", "printf child-ok"], text=True))
print("caps", next(line for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("CapEff:")))
try:
    os.write({inherited_host_fd}, b"modified-through-inherited-fd")
except OSError as error:
    print("inherited-fd blocked", error.errno)
else:
    print("inherited-fd WRITE_SUCCEEDED")

first_child = os.fork()
if first_child == 0:
    os.setsid()
    background = os.fork()
    if background != 0:
        os._exit(0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    namespace_pids = next(
        line for line in Path("/proc/self/status").read_text().splitlines() if line.startswith("NSpid:")
    )
    Path("background-host-pid").write_text(namespace_pids.split()[1])
    while True:
        time.sleep(1)
os.waitpid(first_child, 0)
while not Path("background-host-pid").exists():
    time.sleep(0.01)
            """,
            reset_session=False,
            file_name="isolation.py",
        )
        assert result.exit_code == 0, "".join(result.term_out)
        background_host_pid = int((workspace / "background-host-pid").read_text(encoding="utf-8"))
    finally:
        interpreter.cleanup_session()
        os.close(inherited_host_fd)

    output = "".join(multiprocessing_result.term_out + result.term_out)
    assert "uid 240000 groups []" in output
    assert "multiprocessing semlock-ok" in output
    assert "multiprocessing-tempdir /dev/shm/dojo-multiprocessing" in output
    assert "dataloader-workers 120" in output
    assert "research-imports numpy pandas sklearn torch" in output
    assert f"torch-cuda-available {torch.cuda.is_available()}" in output
    assert "data readable" in output
    assert "home-data readable" in output
    assert "home-instructions True" in output
    assert f"xdg-config {workspace}/.config" in output
    assert "user-site user-site-ok" in output
    assert "outside blocked" in output and "symlink blocked" in output
    assert "data-relative blocked" in output
    assert "data-home blocked" in output
    assert "home-root blocked" in output
    assert "inherited-fd blocked" in output
    assert "WRITE_SUCCEEDED" not in output
    assert "subprocess child-ok" in output
    assert "CapEff:\t0000000000000000" in output
    assert (workspace / "output.txt").read_text(encoding="utf-8") == "workspace-write"
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
    assert data_file.read_text(encoding="utf-8") == "readable"
    assert not host_shm_marker.exists()
    assert Path("/proc/self/mountinfo").read_text(encoding="utf-8") == host_mounts_before
    assert not runtime.exists() or not any(
        path.name.startswith("sandbox-") for path in runtime.iterdir()
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(background_host_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        os.kill(background_host_pid, signal.SIGKILL)
        pytest.fail(f"sandbox background process {background_host_pid} survived cleanup")
    shutil.rmtree(test_root)
