"""Verify that a safetensors checkpoint is tensor-identical to a PyTorch state dict.

The PyTorch file is loaded only with ``weights_only=True`` and only when the running
PyTorch version is at least 2.6, where the CVE-2025-32434 guard is available.  The
receipt is intentionally independent of Hugging Face/Transformers loading logic.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile
from collections import Counter
from typing import Any


SCHEMA = "safetensors-exact-tensor-equivalence-v1"
STATUS = "VERIFIED_EXACT_TENSOR_EQUIVALENCE"
VERSION = re.compile(r"^(\d+)\.(\d+)")


class EquivalenceError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def require_safe_torch_version(version: str) -> None:
    match = VERSION.match(version)
    if match is None or (int(match.group(1)), int(match.group(2))) < (2, 6):
        raise EquivalenceError("PyTorch >=2.6 is required for safe weights_only loading")


def atomic_json(path: pathlib.Path, value: Any) -> None:
    if path.exists() or path.is_symlink():
        raise EquivalenceError("equivalence receipt path must be new")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = pathlib.Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(canonical_json(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify(pytorch_path: pathlib.Path, safetensors_path: pathlib.Path) -> dict[str, Any]:
    for path, label in (
        (pytorch_path, "PyTorch checkpoint"),
        (safetensors_path, "safetensors checkpoint"),
    ):
        if not path.is_file() or path.is_symlink():
            raise EquivalenceError(f"{label} must be a non-symlink regular file")

    import torch
    from safetensors import safe_open

    require_safe_torch_version(torch.__version__)
    state = torch.load(
        pytorch_path, map_location="cpu", weights_only=True, mmap=True
    )
    if not isinstance(state, dict) or not state:
        raise EquivalenceError("PyTorch checkpoint is not a non-empty state dict")
    if any(not isinstance(key, str) for key in state):
        raise EquivalenceError("PyTorch state-dict keys must be strings")

    dtype_counts: Counter[str] = Counter()
    total_numel = 0
    total_bytes = 0
    with safe_open(safetensors_path, framework="pt", device="cpu") as safe:
        safe_keys = set(safe.keys())
        state_keys = set(state)
        if state_keys != safe_keys:
            raise EquivalenceError(
                "checkpoint key sets differ: "
                f"missing={sorted(state_keys - safe_keys)[:5]} "
                f"extra={sorted(safe_keys - state_keys)[:5]}"
            )
        metadata = safe.metadata() or {}
        for key in sorted(state):
            left = state[key]
            if not isinstance(left, torch.Tensor):
                raise EquivalenceError(f"non-tensor value in PyTorch state dict: {key}")
            right = safe.get_tensor(key)
            if left.shape != right.shape or left.dtype != right.dtype:
                raise EquivalenceError(
                    f"tensor shape/dtype differs for {key}: "
                    f"{tuple(left.shape)}/{left.dtype} vs {tuple(right.shape)}/{right.dtype}"
                )
            if not torch.equal(left, right):
                raise EquivalenceError(f"tensor values differ for {key}")
            dtype_counts[str(left.dtype)] += 1
            total_numel += left.numel()
            total_bytes += left.numel() * left.element_size()

    return {
        "schema_version": SCHEMA,
        "status": STATUS,
        "created_utc": utc_now(),
        "torch_version": torch.__version__,
        "safe_loading_guard": "torch>=2.6_weights_only_true",
        "pytorch_path": pytorch_path.resolve().as_posix(),
        "pytorch_sha256": file_sha256(pytorch_path),
        "pytorch_size_bytes": pytorch_path.stat().st_size,
        "safetensors_path": safetensors_path.resolve().as_posix(),
        "safetensors_sha256": file_sha256(safetensors_path),
        "safetensors_size_bytes": safetensors_path.stat().st_size,
        "tensor_count": len(state),
        "total_numel": total_numel,
        "total_tensor_bytes": total_bytes,
        "dtype_counts": dict(sorted(dtype_counts.items())),
        "safetensors_metadata": dict(sorted(metadata.items())),
        "key_sets_identical": True,
        "shapes_identical": True,
        "dtypes_identical": True,
        "values_bitwise_identical": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pytorch", required=True)
    parser.add_argument("--safetensors", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        result = verify(
            pathlib.Path(args.pytorch).resolve(),
            pathlib.Path(args.safetensors).resolve(),
        )
        atomic_json(pathlib.Path(args.receipt).resolve(), result)
    except (EquivalenceError, OSError, ValueError, RuntimeError) as exc:
        print(f"SAFETENSORS_EQUIVALENCE_ERROR: {exc}", file=sys.stderr)
        return 2
    print(canonical_json(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
