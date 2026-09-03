"""Integrity and cursor gate for our own bounded synthetic Accelerate checkpoints.

This is deliberately NOT a loader for research or third-party checkpoints.  A
hash proves integrity against the caller's receipt, not trust in arbitrary
pickle.  The only caller currently approved is the two-parameter CPU harness.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re


MAX_FILE_BYTES = 1024 * 1024
COMPONENTS = ("model", "optimizer", "python_rng", "numpy_rng", "torch_rng")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_binding(binding):
    if (binding.get("scope") != "synthetic-two-parameter-cpu-only"
            or type(binding.get("world")) is not int or binding["world"] not in (2, 4)
            or binding.get("arm") not in ("G_to_L", "Ghash_to_L")
            or binding.get("seed") != 6
            or binding.get("base_commit") != "dca429b85507cfcd96b256f65e2df2ac15be7b9a"):
        raise ValueError("checkpoint_scope_or_binding_mismatch")
    for name in ("plan_sha256", "input_sha256", "runtime_sha256", "sources_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(binding.get(name))):
            raise ValueError("invalid_checkpoint_binding_hash")


def expected_files(world):
    if type(world) is not int or world not in (2, 4):
        raise ValueError("unsupported_checkpoint_world")
    return {"model.safetensors", "optimizer.bin"} | {
        f"{stem}_{rank}.{extension}"
        for rank in range(world)
        for stem, extension in (("random_states", "pkl"), ("observed", "json"))
    }


def _regular(path):
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE_BYTES:
        raise ValueError("unsafe_checkpoint_file")


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".partial")
    if path.exists() or temporary.exists():
        raise ValueError("checkpoint_overwrite_forbidden")
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def seal(root, binding, completed_steps, accelerator_step):
    """Called after every rank has saved; the manifest is the completion marker."""
    validate_binding(binding)
    if type(completed_steps) is not int or completed_steps not in (2, 3, 4):
        raise ValueError("invalid_plan_checkpoint_cursor")
    if type(accelerator_step) is not int or accelerator_step != 0:
        raise ValueError("unexpected_accelerator_internal_step")
    expected = expected_files(binding["world"])
    if root.is_symlink() or {p.name for p in root.iterdir()} != expected:
        raise ValueError("checkpoint_file_set_mismatch")
    for name in expected:
        _regular(root / name)
    manifest = {
        "binding": binding,
        "completed_steps": completed_steps,
        "accelerator_internal_step": accelerator_step,
        "files": {name: {"sha256": sha(root / name), "bytes": (root / name).stat().st_size}
                  for name in sorted(expected)},
    }
    atomic_json(root / "manifest.json", manifest)
    return sha(root / "manifest.json")


def verify(root, binding, completed_steps, manifest_sha256):
    """Validate ALL ranks and files before ANY checkpoint deserialization."""
    validate_binding(binding)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_checkpoint_directory")
    path = root / "manifest.json"
    _regular(path)
    if sha(path) != manifest_sha256:
        raise ValueError("checkpoint_manifest_hash_mismatch")
    manifest = json.loads(path.read_text())
    if (manifest.get("binding") != binding
            or type(completed_steps) is not int or completed_steps not in (2, 3, 4)
            or manifest.get("completed_steps") != completed_steps
            or manifest.get("accelerator_internal_step") != 0):
        raise ValueError("checkpoint_cursor_or_binding_mismatch")
    expected = expected_files(binding["world"])
    if (set(manifest.get("files", {})) != expected
            or {p.name for p in root.iterdir()} != expected | {"manifest.json"}):
        raise ValueError("checkpoint_file_set_mismatch")
    for name, receipt in manifest["files"].items():
        target = root / name
        _regular(target)
        if target.stat().st_size != receipt["bytes"] or sha(target) != receipt["sha256"]:
            raise ValueError("checkpoint_file_hash_mismatch")
    for rank in range(binding["world"]):
        observed = json.loads((root / f"observed_{rank}.json").read_text())
        if (observed.get("rank") != rank or observed.get("completed_steps") != completed_steps
                or observed.get("binding") != binding or set(observed.get("state", {})) != set(COMPONENTS)):
            raise ValueError("checkpoint_rank_receipt_mismatch")
    return manifest


def verify_restored(expected, actual):
    """Do not trust load_state returning: its RNG loader catches exceptions."""
    if set(expected) != set(COMPONENTS) or set(actual) != set(COMPONENTS):
        raise ValueError("restored_state_component_set_mismatch")
    for key in COMPONENTS:
        if expected[key] != actual[key]:
            raise ValueError("restored_state_mismatch:" + key)
