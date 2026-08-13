"""Fail-silent identity wrapper that materializes the first compatible test prediction."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from pathlib import Path
from typing import Any


_LOCK = threading.Lock()
_DONE = False
_START = time.monotonic()


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        # Directory handles are not opened with POSIX O_DIRECTORY semantics on Windows.
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sample_path() -> Path:
    configured = os.environ.get("SPT_SAMPLE_SUBMISSION")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path
        raise FileNotFoundError(path)
    matches = sorted(Path("data").rglob("sample_submission.csv"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one sample_submission.csv, got {len(matches)}")
    return matches[0]


def _numpy(value: Any):
    import numpy as np

    candidate = value
    if hasattr(candidate, "detach"):
        candidate = candidate.detach()
    if hasattr(candidate, "cpu"):
        candidate = candidate.cpu()
    if hasattr(candidate, "numpy"):
        candidate = candidate.numpy()
    array = np.asarray(candidate)
    if array.ndim not in (1, 2) or array.size == 0:
        raise ValueError(f"unsupported prediction shape: {array.shape}")
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"non-numeric prediction dtype: {array.dtype}")
    array = array.astype(float, copy=False)
    if not np.isfinite(array).all():
        raise ValueError("non-finite prediction")
    return array


def _candidate_frame(value: Any, method: str):
    import pandas as pd

    sample = pd.read_csv(_sample_path())
    array = _numpy(value)
    if len(array) != len(sample) or len(sample.columns) < 2:
        raise ValueError(f"row/schema mismatch prediction={len(array)} sample={sample.shape}")
    columns = list(sample.columns)
    frame = sample.copy(deep=True)
    target_width = len(columns) - 1
    if array.ndim == 1 and target_width == 1:
        prediction = array.reshape(-1, 1)
        targets = columns[-1:]
    else:
        if array.ndim != 2:
            raise ValueError(
                f"one-dimensional prediction requires exactly one target column: {len(columns)}"
            )
        width = int(array.shape[1])
        if width == 1 and target_width == 1:
            prediction = array
            targets = columns[-1:]
        elif method == "predict_proba" and width == 2 and target_width == 1:
            prediction = array[:, 1].reshape(-1, 1)
            targets = columns[-1:]
        elif width == target_width:
            prediction = array
            targets = columns[-width:]
        else:
            raise ValueError(f"prediction width {width} incompatible with sample width {len(columns)}")
    for index, name in enumerate(targets):
        frame[name] = prediction[:, index]
    return frame


def _write_probe(frame, method: str, callsite: str, argument: str) -> None:
    destination = Path("candidate_probe.csv")
    temporary = Path(f".candidate_probe.{os.getpid()}.tmp")
    if destination.exists() or temporary.exists():
        raise FileExistsError(destination)
    try:
        frame.to_csv(temporary, index=False)
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        _fsync_dir(destination.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    elapsed = time.monotonic() - _START
    print(
        "CANDIDATE_PROBE_READY "
        f"elapsed_s={elapsed:.6f} sha256={digest}",
        flush=True,
    )
    print(
        "SPT_CAPTURE "
        f"method={method} callsite={callsite}",
        flush=True,
    )


def capture(value: Any, method: str, callsite: str, argument: str) -> Any:
    """Attempt one side-effect-only capture and return the exact input object."""
    global _DONE
    if _DONE:
        return value
    with _LOCK:
        if _DONE:
            return value
        try:
            frame = _candidate_frame(value, method)
            _write_probe(frame, method, callsite, argument)
        except Exception:
            return value
        _DONE = True
    return value
