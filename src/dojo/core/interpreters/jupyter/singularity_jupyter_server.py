# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from __future__ import annotations

import atexit
import json
import logging
import os
import re
import secrets
import select
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import TracebackType

from .base import JupyterConnectable, JupyterConnectionInfo
from .jupyter_client import JupyterClient

log = logging.getLogger(__name__)

_CONTAINER_WORKING_DIR = Path("/workspace")
_CONTAINER_HOME = _CONTAINER_WORKING_DIR / ".home"
_JUPYTER_RUNTIME_DIR = _CONTAINER_HOME / ".local/share/jupyter/runtime"
_PYTHON_USER_BASE = _CONTAINER_WORKING_DIR / ".local"
_ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_READY_PATTERN = re.compile(r"is available at http://([^:]+):(\d+)")
_DEFAULT_STARTUP_TIMEOUT_SECONDS = 300.0
_JUPYTER_BOOTSTRAP = (
    "import runpy, site; from pathlib import Path; "
    "Path(site.getusersitepackages()).mkdir(parents=True, exist_ok=True); "
    "runpy.run_module('jupyter', run_name='__main__')"
)
_SINGULARITY_RUNTIME_ENV_TO_CLEAR = {
    "SINGULARITY_BIND",
    "SINGULARITY_BINDPATH",
    "SINGULARITY_HOME",
    "SINGULARITY_OVERLAY",
    "SINGULARITY_WORKDIR",
}


def _resolve_superimage_path(
    superimage_directory: str | Path, superimage_version: str
) -> Path:
    if not superimage_directory:
        raise ValueError(
            "superimage_directory must be set for the Singularity runtime."
        )
    if not superimage_version:
        raise ValueError("superimage_version must be set for the Singularity runtime.")

    image_path = (
        Path(superimage_directory).expanduser()
        / f"superimage.root.{superimage_version}.sif"
    ).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Singularity superimage does not exist: {image_path}")
    return image_path


def _normalise_read_only_binds(read_only_binds: Mapping[str, str]) -> dict[Path, Path]:
    binds: dict[Path, Path] = {}
    for source, destination in read_only_binds.items():
        source_path = Path(source).expanduser().resolve()
        destination_path = Path(destination)
        if not destination_path.is_absolute():
            destination_path = Path("/root") / destination_path
        binds[source_path] = destination_path
    return binds


def _build_container_environment(
    configured_env: Mapping[str, str], host_env: Mapping[str, str] | None = None
) -> dict[str, str]:
    container_env = {
        "HOME": str(_CONTAINER_HOME),
        "JUPYTER_RUNTIME_DIR": str(_JUPYTER_RUNTIME_DIR),
        "PYTHONUSERBASE": str(_PYTHON_USER_BASE),
        "PYTHONUNBUFFERED": "1",
        "WANDB_DISABLED": "1",
        "TQDM_DISABLE": "1",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "CUDA_LAUNCH_BLOCKING": "1",
        "TF_CPP_MIN_LOG_LEVEL": "3",
    }
    host_env = os.environ if host_env is None else host_env
    for name in ("CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER"):
        host_value = host_env.get(name)
        configured_value = configured_env.get(name)
        if host_value is not None:
            if configured_value is not None and str(configured_value) != host_value:
                raise ValueError(
                    f"interpreter.env cannot override launcher-assigned {name}: "
                    f"configured {configured_value!r}, assigned {host_value!r}"
                )
            container_env[name] = host_value

    for name, value in configured_env.items():
        if not _ENV_NAME_PATTERN.fullmatch(name):
            raise ValueError(f"Invalid container environment variable name: {name!r}")
        container_env[name] = str(value)
    return container_env


def _build_runtime_environment(host_env: Mapping[str, str]) -> dict[str, str]:
    runtime_env = {
        name: value
        for name, value in host_env.items()
        if not name.startswith("SINGULARITYENV_")
    }
    for name in _SINGULARITY_RUNTIME_ENV_TO_CLEAR:
        runtime_env.pop(name, None)
    return runtime_env


def _process_start_ticks(pid: int) -> int | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        return int(stat.rsplit(")", 1)[1].split()[19])
    except (FileNotFoundError, IndexError, ValueError, OSError):
        return None


def _publish_container_identity(pid: int | None) -> None:
    identity_path = os.environ.get("DOJO_WORKER_IDENTITY_PATH", "")
    if not identity_path:
        return
    path = Path(identity_path)
    try:
        with path.open("r", encoding="utf-8") as file:
            identity = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return

    if pid is None:
        identity.update(
            {
                "container_pid": None,
                "container_pgid": None,
                "container_process_start_ticks": None,
            }
        )
    else:
        try:
            process_group = os.getpgid(pid)
        except ProcessLookupError:
            process_group = None
        identity.update(
            {
                "container_pid": pid,
                "container_pgid": process_group,
                "container_process_start_ticks": _process_start_ticks(pid),
            }
        )
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(identity, file, indent=2, sort_keys=True)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    except OSError:
        temporary_path.unlink(missing_ok=True)
        log.exception("Could not publish Singularity process identity to %s", path)


def _build_singularity_command(
    *,
    runtime_executable: str,
    image_path: Path,
    working_dir: Path,
    bind_inputs_dir: Path | None,
    read_only_overlays: Sequence[Path],
    read_only_binds: Mapping[Path, Path],
    container_env: Mapping[str, str],
    token: str,
    port: int | None = None,
) -> list[str]:
    args = [
        runtime_executable,
        "exec",
        "--containall",
        "--cleanenv",
        "--no-home",
        "--nv",
    ]

    for overlay in read_only_overlays:
        args.extend(["--overlay", f"{overlay}:ro"])

    args.extend(["--bind", f"{working_dir}:{_CONTAINER_WORKING_DIR}:rw"])
    if bind_inputs_dir is not None:
        args.extend(
            ["--bind", f"{bind_inputs_dir}:{_CONTAINER_WORKING_DIR / 'data'}:ro"]
        )
    for source, destination in read_only_binds.items():
        args.extend(["--bind", f"{source}:{destination}:ro"])

    args.extend(
        [
            "--pwd",
            str(_CONTAINER_WORKING_DIR),
            str(image_path),
            "env",
            *(f"{name}={value}" for name, value in container_env.items()),
            "python",
            "-c",
            _JUPYTER_BOOTSTRAP,
            "kernelgateway",
            "--KernelGatewayApp.auth_token",
            token,
            "--JupyterApp.answer_yes=True",
            "--JupyterWebsocketPersonality.list_kernels=True",
            "--KernelGatewayApp.answer_yes=True",
            "--KernelManager.cache_ports=False",
        ]
    )
    if port is not None:
        args.append(f"--KernelGatewayApp.port={port}")
    return args


def _redact_command(args: Sequence[str]) -> list[str]:
    redacted = list(args)
    redact_next = False
    for index, arg in enumerate(redacted):
        if redact_next:
            redacted[index] = "<redacted>"
            redact_next = False
            continue
        if arg == "--KernelGatewayApp.auth_token":
            redact_next = True
            continue
        if "=" in arg:
            name, _ = arg.split("=", 1)
            if any(
                marker in name.upper()
                for marker in ("TOKEN", "KEY", "PASSWORD", "SECRET")
            ):
                redacted[index] = f"{name}=<redacted>"
    return redacted


class SingularityJupyterServer(JupyterConnectable):
    def __init__(
        self,
        token: str | None = None,
        working_dir: Path | str | None = None,
        bind_inputs_dir: Path | str | None = None,
        superimage_directory: Path | str | None = None,
        superimage_version: str | None = None,
        read_only_overlays: Sequence[str] | None = None,
        read_only_binds: Mapping[str, str] | None = None,
        env: Mapping[str, str] | None = None,
        port: int | None = None,
        startup_timeout: float = _DEFAULT_STARTUP_TIMEOUT_SECONDS,
    ) -> None:
        self._subprocess: subprocess.Popen[str] | None = None
        self._output_thread: threading.Thread | None = None

        runtime_executable = shutil.which("singularity")
        if runtime_executable is None:
            raise RuntimeError(
                "The Singularity runtime was selected, but `singularity` was not found in PATH."
            )

        if working_dir is None:
            raise ValueError("working_dir must be set for the Singularity runtime.")
        host_working_dir = Path(working_dir).expanduser().resolve()
        if not host_working_dir.is_dir():
            raise FileNotFoundError(
                f"Jupyter working directory does not exist: {host_working_dir}"
            )
        (host_working_dir / ".home/.local/share/jupyter/runtime").mkdir(
            parents=True, exist_ok=True
        )
        (host_working_dir / ".local").mkdir(parents=True, exist_ok=True)

        host_inputs_dir = None
        if bind_inputs_dir is not None:
            host_inputs_dir = Path(bind_inputs_dir).expanduser().resolve()
            if not host_inputs_dir.is_dir():
                raise FileNotFoundError(
                    f"Jupyter input data directory does not exist: {host_inputs_dir}"
                )

        overlays = [
            Path(path).expanduser().resolve() for path in read_only_overlays or []
        ]
        for overlay in overlays:
            if not overlay.exists():
                raise FileNotFoundError(
                    f"Read-only Singularity overlay does not exist: {overlay}"
                )

        binds = _normalise_read_only_binds(read_only_binds or {})
        for source in binds:
            if not source.exists():
                raise FileNotFoundError(
                    f"Read-only Singularity bind source does not exist: {source}"
                )

        if token is None:
            token = secrets.token_hex(32)
        self.token = token

        image_path = _resolve_superimage_path(
            superimage_directory or "", superimage_version or ""
        )
        container_env = _build_container_environment(env or {})
        args = _build_singularity_command(
            runtime_executable=runtime_executable,
            image_path=image_path,
            working_dir=host_working_dir,
            bind_inputs_dir=host_inputs_dir,
            read_only_overlays=overlays,
            read_only_binds=binds,
            container_env=container_env,
            token=token,
            port=port,
        )

        try:
            version = subprocess.run(
                [runtime_executable, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            version = "version unavailable"
        log.warning("Starting Jupyter with %s", version)
        log.warning("Singularity image: %s", image_path)
        log.warning("Singularity working directory: %s", host_working_dir)
        log.warning(
            "Singularity container environment variables: %s", sorted(container_env)
        )
        log.warning("Singularity command: %s", _redact_command(args))

        try:
            self._subprocess = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
                env=_build_runtime_environment(os.environ),
            )
            _publish_container_identity(self._subprocess.pid)
            self._wait_until_ready(startup_timeout)
        except BaseException:
            self.stop()
            raise

        self._output_thread = threading.Thread(
            target=self._drain_output,
            name=f"singularity-jupyter-{self._subprocess.pid}",
            daemon=True,
        )
        self._output_thread.start()
        atexit.register(self.stop)

    def _wait_until_ready(self, startup_timeout: float) -> None:
        process = self._subprocess
        if process is None or process.stdout is None:
            raise RuntimeError(
                "Singularity Jupyter process was not started with an output pipe."
            )

        deadline = time.monotonic() + startup_timeout
        startup_output: list[str] = []
        while True:
            result = process.poll()
            if result is not None:
                startup_output.extend(process.stdout.readlines())
                output = "".join(startup_output)
                raise RuntimeError(
                    f"Singularity Jupyter server failed to start with exit code {result}. Output:\n{output}"
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                output = "".join(startup_output)
                raise TimeoutError(
                    f"Singularity Jupyter server did not become ready within {startup_timeout:g} seconds. "
                    f"Output:\n{output}"
                )

            readable, _, _ = select.select(
                [process.stdout], [], [], min(1.0, remaining)
            )
            if not readable:
                continue

            line = process.stdout.readline()
            if not line:
                continue
            startup_output.append(line)
            log.warning(line.rstrip("\n"))

            match = _READY_PATTERN.search(line)
            if match:
                self.ip = match.group(1)
                self.port = int(match.group(2))
                return

    def _drain_output(self) -> None:
        process = self._subprocess
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            log.warning(line.rstrip("\n"))

    def stop(self) -> None:
        process = self._subprocess
        if process is None:
            return

        log.warning("Stopping Singularity Jupyter server...")
        if process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=120)
            except subprocess.TimeoutExpired:
                log.error(
                    "Singularity Jupyter server did not terminate; sending SIGKILL."
                )
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()

        self._subprocess = None
        _publish_container_identity(None)
        output_thread = self._output_thread
        if (
            output_thread is not None
            and output_thread is not threading.current_thread()
        ):
            output_thread.join(timeout=5)
        self._output_thread = None
        try:
            atexit.unregister(self.stop)
        except Exception:
            pass
        log.warning("Singularity Jupyter server terminated.")

    @property
    def connection_info(self) -> JupyterConnectionInfo:
        return JupyterConnectionInfo(
            host=self.ip, use_https=False, port=self.port, token=self.token
        )

    def get_client(self) -> JupyterClient:
        return JupyterClient(self.connection_info)

    def __enter__(self) -> SingularityJupyterServer:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass
