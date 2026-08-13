from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("SUPERIMAGE_DIR", ".")

# The repository's interpreter registry imports runtime classes eagerly. Loading
# the config package first follows the same import order as the application.
from dojo.config_dataclasses.interpreter.jupyter import (  # noqa: E402,F401
    JupyterInterpreterConfig as _JupyterConfig,
)
from dojo.core.interpreters.jupyter import jupyter_interpreter  # noqa: E402
from dojo.core.interpreters.jupyter.singularity_jupyter_server import (  # noqa: E402
    _build_container_environment,
    _build_runtime_environment,
    _build_singularity_command,
    _normalise_read_only_binds,
    _redact_command,
    _resolve_superimage_path,
)


def test_resolve_superimage_path(tmp_path: Path) -> None:
    image = tmp_path / "superimage.root.test-v1.sif"
    image.touch()

    assert _resolve_superimage_path(tmp_path, "test-v1") == image


def test_resolve_superimage_path_requires_existing_image(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="superimage does not exist"):
        _resolve_superimage_path(tmp_path, "missing")


def test_jupyter_config_rejects_unknown_runtime(tmp_path: Path) -> None:
    cfg = _JupyterConfig(
        container_runtime="docker",
        superimage_directory=str(tmp_path),
        working_dir=str(tmp_path),
        timeout=60,
    )

    with pytest.raises(ValueError, match="Unsupported container runtime"):
        cfg.validate()


def test_container_environment_is_runtime_independent_and_extensible() -> None:
    container_env = _build_container_environment(
        {
            "HOME": "/custom-home",
            "CUSTOM_VALUE": "value with spaces",
        }
    )

    assert container_env["HOME"] == "/custom-home"
    assert container_env["CUSTOM_VALUE"] == "value with spaces"
    assert container_env["PYTHONUSERBASE"] == "/workspace/.local"


def test_container_environment_rejects_invalid_names() -> None:
    with pytest.raises(ValueError, match="Invalid container environment variable"):
        _build_container_environment({"INVALID-NAME": "value"})


def test_runtime_environment_ignores_implicit_container_configuration() -> None:
    runtime_env = _build_runtime_environment(
        {
            "PATH": "/bin",
            "SINGULARITY_CACHEDIR": "/cache",
            "SINGULARITY_BIND": "/unexpected:/bind",
            "SINGULARITYENV_HOME": "/unexpected-home",
        }
    )

    assert runtime_env == {"PATH": "/bin", "SINGULARITY_CACHEDIR": "/cache"}


def test_build_singularity_command_uses_foreground_exec_and_explicit_binds(
    tmp_path: Path,
) -> None:
    working_dir = tmp_path / "working"
    data_dir = tmp_path / "data"
    overlay = tmp_path / "base.img"
    extra_source = tmp_path / "models"
    image = tmp_path / "superimage.root.test.sif"
    for directory in (working_dir, data_dir, extra_source):
        directory.mkdir()
    overlay.touch()
    image.touch()

    args = _build_singularity_command(
        runtime_executable="/bin/singularity",
        image_path=image,
        working_dir=working_dir,
        bind_inputs_dir=data_dir,
        read_only_overlays=[overlay],
        read_only_binds={extra_source: Path("/root/models")},
        container_env={"HOME": "/workspace/.home", "CUSTOM_VALUE": "value with spaces"},
        token="secret-token",
    )

    assert args[:3] == ["/bin/singularity", "exec", "--containall"]
    assert "instance" not in args
    assert ["--overlay", f"{overlay}:ro"] == args[
        args.index("--overlay") : args.index("--overlay") + 2
    ]
    assert f"{working_dir}:/workspace:rw" in args
    assert f"{data_dir}:/workspace/data:ro" in args
    assert f"{extra_source}:/root/models:ro" in args
    assert args[args.index(str(image)) + 1 : args.index("python")] == [
        "env",
        "HOME=/workspace/.home",
        "CUSTOM_VALUE=value with spaces",
    ]
    assert args[args.index("python") + 1] == "-c"
    assert "site.getusersitepackages()" in args[args.index("python") + 2]


def test_build_singularity_command_uses_explicit_gateway_port(tmp_path: Path) -> None:
    image = tmp_path / "superimage.root.test.sif"
    working_dir = tmp_path / "working"
    image.touch()
    working_dir.mkdir()

    args = _build_singularity_command(
        runtime_executable="/bin/singularity",
        image_path=image,
        working_dir=working_dir,
        bind_inputs_dir=None,
        read_only_overlays=[],
        read_only_binds={},
        container_env={"HOME": "/workspace/.home"},
        token="secret-token",
        port=23456,
    )

    assert "--KernelGatewayApp.port=23456" in args
    assert "--KernelGatewayApp.port_retries=0" not in args


def test_relative_read_only_bind_targets_keep_apptainer_semantics(
    tmp_path: Path,
) -> None:
    source = tmp_path / "models"
    source.mkdir()

    assert _normalise_read_only_binds({str(source): ".cache/models"}) == {
        source: Path("/root/.cache/models")
    }


def test_command_logging_redacts_tokens_and_keys() -> None:
    args = [
        "env",
        "HF_TOKEN=top-secret",
        "SSH_PUBLIC_KEY=public-key",
        "python",
        "--KernelGatewayApp.auth_token",
        "gateway-secret",
    ]

    assert _redact_command(args) == [
        "env",
        "HF_TOKEN=<redacted>",
        "SSH_PUBLIC_KEY=<redacted>",
        "python",
        "--KernelGatewayApp.auth_token",
        "<redacted>",
    ]


def test_jupyter_interpreter_routes_to_singularity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, object]] = []

    class FakeSingularityServer:
        def __init__(self, **kwargs: object) -> None:
            calls.append(kwargs)

        def stop(self) -> None:
            pass

    monkeypatch.setattr(
        jupyter_interpreter, "SingularityJupyterServer", FakeSingularityServer
    )
    cfg = SimpleNamespace(
        timeout=60,
        strip_ansi=True,
        container_runtime="singularity",
        working_dir=str(tmp_path / "workspace"),
        superimage_directory=str(tmp_path),
        superimage_version="test",
        read_only_overlays=[],
        read_only_binds={},
        env={},
    )

    interpreter = jupyter_interpreter.JupyterInterpreter(cfg)

    assert calls[0]["working_dir"] == (tmp_path / "workspace").resolve()
    assert calls[0]["bind_inputs_dir"] == (tmp_path / "workspace/data").resolve()
    interpreter.close()
